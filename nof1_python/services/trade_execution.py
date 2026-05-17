"""
Trade execution service module.
Handles order placement, closing, and status queries via Binance Futures.
"""
from binance.client import Client as _Client
from typing import Dict, List, Optional
from datetime import datetime, timezone
import logging
import time

from config.config import settings
from utils.time_utils import get_utc_now
from utils.retry import retry_with_backoff

logger = logging.getLogger(__name__)


class TradeExecutionService:
    """Service for executing trades on Binance Futures."""

    def __init__(self):
        """Initialize Binance Futures client."""
        from binance.client import Client as _Client

        # monkey-patch ping() 避免 init 时访问不可达的 URL
        _Client.ping = lambda self: None

        proxy = getattr(settings, 'HTTP_PROXY', None) or getattr(settings, 'HTTPS_PROXY', None)
        requests_params = {'timeout': 60, 'verify': False}
        if proxy:
            requests_params['proxies'] = {'http': proxy, 'https': proxy}

        self.client = _Client(
            api_key=settings.BINANCE_API_KEY,
            api_secret=settings.BINANCE_API_SECRET,
            testnet=False,
            requests_params=requests_params
        )

        if settings.BINANCE_TESTNET:
            self.client.API_URL = 'https://testnet.binance.vision/api'
            self.client.FUTURES_URL = 'https://testnet.binancefuture.com/fapi'

        if proxy:
            self.client.session.proxies = {'http': proxy, 'https': proxy}
        # 禁用 SSL 验证（Clash 代理对 testnet.binancefuture.com SSL 握手有问题）
        self.client.session.verify = False

        # 同步服务器时间戳偏移（避免 -1021 错误）
        try:
            from utils.time_utils import get_binance_timestamp_offset
            proxy = getattr(settings, 'HTTP_PROXY', None) or getattr(settings, 'HTTPS_PROXY', None)
            offset = get_binance_timestamp_offset(proxy_url=proxy, verify_ssl=False)
            self.client.timestamp_offset = offset
        except Exception as e:
            logger.warning(f"Could not sync timestamp: {e}")
            self.client.timestamp_offset = 0

        logger.info(f"TradeExecutionService initialized (testnet={settings.BINANCE_TESTNET})")

    @retry_with_backoff(max_retries=3, base_delay=1.0, max_delay=8.0,
                        exceptions=(Exception,))
    def open_position(
        self,
        symbol: str,
        side: str,
        leverage: int,
        amount_usdt: float
    ) -> Dict:
        """
        Open a new futures position (market order).

        Args:
            symbol: Trading pair (e.g., "BTCUSDT")
            side: "LONG" or "SHORT"
            leverage: Leverage multiplier (1-125)
            amount_usdt: Amount in USDT to use

        Returns:
            Dict: Order response
        """
        try:
            self.client.futures_change_leverage(symbol=symbol, leverage=leverage)
            logger.info(f"Set leverage={leverage} for {symbol}")

            ticker = self.client.futures_symbol_ticker(symbol=symbol)
            current_price = float(ticker["price"])
            quantity = round(amount_usdt / current_price * leverage, 4)

            order_side = "BUY" if side.upper() == "LONG" else "SELL"
            order = self.client.futures_create_order(
                symbol=symbol,
                side=order_side,
                type="MARKET",
                quantity=quantity
            )

            logger.info(f"Opened {side} position: {symbol}, qty={quantity}, order_id={order.get('orderId')}")
            return {
                "order_id": str(order.get("orderId")),
                "symbol": symbol,
                "side": side,
                "quantity": quantity,
                "price": current_price,
                "status": order.get("status", "FILLED"),
                "timestamp": get_utc_now()
            }

        except Exception as e:
            logger.error(f"Error opening position: {e}", exc_info=True)
            raise

    @retry_with_backoff(max_retries=3, base_delay=1.0, max_delay=8.0,
                        exceptions=(Exception,))
    def close_position(
        self,
        symbol: str,
        position_side: str = "BOTH",
        percentage: float = 100.0
    ) -> List[Dict]:
        """
        Close a position (partially or fully).

        Args:
            symbol: Trading pair
            position_side: "LONG", "SHORT", or "BOTH"
            percentage: Percentage to close (1-100)

        Returns:
            List[Dict]: List of order responses
        """
        try:
            positions = self.client.futures_position_information(symbol=symbol)
            if not positions:
                logger.warning(f"No position found for {symbol}")
                return []

            position = positions[0]
            current_qty = float(position["positionAmt"])

            if current_qty == 0:
                logger.warning(f"Position size is 0 for {symbol}")
                return []

            close_qty = abs(current_qty) * (percentage / 100.0)
            close_qty = round(close_qty, 4)

            if current_qty > 0:
                order_side = "SELL"
            else:
                order_side = "BUY"

            order = self.client.futures_create_order(
                symbol=symbol,
                side=order_side,
                type="MARKET",
                quantity=close_qty
            )

            logger.info(f"Closed {percentage}% of position: {symbol}, qty={close_qty}, order_id={order.get('orderId')}")
            return [{
                "order_id": str(order.get("orderId")),
                "symbol": symbol,
                "side": order_side,
                "quantity": close_qty,
                "status": order.get("status", "FILLED"),
                "timestamp": get_utc_now()
            }]

        except Exception as e:
            logger.error(f"Error closing position: {e}", exc_info=True)
            raise

    @retry_with_backoff(max_retries=3, base_delay=1.0, max_delay=8.0,
                        exceptions=(Exception,))
    def cancel_order(self, symbol: str, order_id: str) -> Dict:
        """
        Cancel an open order.

        Args:
            symbol: Trading pair
            order_id: Order ID to cancel

        Returns:
            Dict: Cancellation response
        """
        try:
            result = self.client.futures_cancel_order(symbol=symbol, orderId=int(order_id))
            logger.info(f"Cancelled order {order_id} for {symbol}")
            return {
                "order_id": str(result.get("orderId")),
                "status": "CANCELED",
                "symbol": symbol
            }
        except Exception as e:
            logger.error(f"Error cancelling order {order_id}: {e}", exc_info=True)
            raise

    @retry_with_backoff(max_retries=3, base_delay=1.0, max_delay=8.0,
                        exceptions=(Exception,))
    def get_order_status(self, symbol: str, order_id: str) -> Dict:
        """
        Check order status.

        Args:
            symbol: Trading pair
            order_id: Order ID to check

        Returns:
            Dict: Order status information
        """
        try:
            order = self.client.futures_get_order(symbol=symbol, orderId=int(order_id))
            return {
                "order_id": str(order.get("orderId")),
                "symbol": order.get("symbol"),
                "status": order.get("status"),
                "side": order.get("side"),
                "type": order.get("type"),
                "price": float(order.get("price", 0)),
                "quantity": float(order.get("origQty", 0)),
                "executed_qty": float(order.get("executedQty", 0)),
                "avg_price": float(order.get("avgPrice", 0)),
                "timestamp": datetime.fromtimestamp(order.get("time", 0) / 1000, tz=timezone.utc)
            }
        except Exception as e:
            logger.error(f"Error checking order status {order_id}: {e}", exc_info=True)
            raise

    @retry_with_backoff(max_retries=3, base_delay=1.0, max_delay=8.0,
                        exceptions=(Exception,))
    def get_open_orders(self, symbol: str = None) -> List[Dict]:
        """
        Get all open orders.

        Args:
            symbol: Optional trading pair filter

        Returns:
            List[Dict]: List of open orders
        """
        try:
            if symbol:
                orders = self.client.futures_get_open_orders(symbol=symbol)
            else:
                orders = self.client.futures_get_open_orders()

            result = []
            for o in orders:
                result.append({
                    "order_id": str(o["orderId"]),
                    "symbol": o["symbol"],
                    "side": o["side"],
                    "type": o["type"],
                    "price": float(o["price"]) if o["price"] else 0.0,
                    "quantity": float(o["origQty"]),
                    "status": o["status"],
                    "timestamp": datetime.fromtimestamp(o["time"] / 1000, tz=timezone.utc)
                })
            return result
        except Exception as e:
            logger.error(f"Error fetching open orders: {e}", exc_info=True)
            raise
