"""
Account manager module.
Syncs account status, queries positions.
"""
from binance.client import Client as _Client
from typing import List, Dict, Optional
from datetime import datetime, timezone
import logging
import time

from config.config import settings
from utils.time_utils import get_utc_now

logger = logging.getLogger(__name__)


class AccountManager:
    """Service for managing account data from Binance Futures."""

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

        logger.info(f"AccountManager initialized (testnet={settings.BINANCE_TESTNET})")

    def get_account_balance(self) -> Dict:
        """
        Get futures account balance and PnL.

        Returns:
            Dict: Account balance information
        """
        try:
            account = self.client.futures_account()
            total_wallet = float(account.get("totalWalletBalance", 0))
            unrealized_profit = float(account.get("totalUnrealizedProfit", 0))
            return_percent = (unrealized_profit / total_wallet * 100) if total_wallet > 0 else 0
            
            logger.debug(f"Fetched account balance: totalWallet={total_wallet}, unrealizedProfit={unrealized_profit}")
            return {
                "total_wallet_balance": total_wallet,
                "total_unrealized_profit": unrealized_profit,
                "total_margin_balance": float(account.get("totalMarginBalance", 0)),
                "available_balance": float(account.get("availableBalance", 0)),
                "return_percent": return_percent,
                "timestamp": get_utc_now()
            }
        except Exception as e:
            logger.error(f"Error fetching account balance: {e}", exc_info=True)
            raise

    def get_positions(self, symbol: str = None) -> List[Dict]:
        """
        Get current futures positions.

        Args:
            symbol: Optional symbol filter (e.g. "BTCUSDT")

        Returns:
            List[Dict]: List of non-zero positions
        """
        try:
            if symbol:
                positions = self.client.futures_position_information(symbol=symbol)
            else:
                positions = self.client.futures_position_information()

            result = []
            for p in positions:
                position_amt = float(p["positionAmt"])
                if position_amt != 0:
                    result.append({
                        "symbol": p["symbol"],
                        "side": "LONG" if position_amt > 0 else "SHORT",
                        "quantity": abs(position_amt),
                        "entry_price": float(p["entryPrice"]),
                        "mark_price": float(p["markPrice"]),
                        "unrealized_pnl": float(p["unrealizedProfit"]),
                        "leverage": int(p["leverage"]),
                        "liquidation_price": float(p["liquidationPrice"]) if p["liquidationPrice"] != "0" else None,
                        "timestamp": get_utc_now()
                    })

            logger.debug(f"Fetched {len(result)} active position(s)")
            return result
        except Exception as e:
            logger.error(f"Error fetching positions: {e}", exc_info=True)
            raise

    def get_all_orders(self, symbol: str = None, limit: int = 20) -> List[Dict]:
        """
        Get recent orders (all statuses).

        Args:
            symbol: Optional symbol filter
            limit: Number of orders (max 1000)

        Returns:
            List[Dict]: List of orders
        """
        try:
            if symbol:
                orders = self.client.futures_get_all_orders(symbol=symbol, limit=limit)
            else:
                orders = self.client.futures_get_all_orders(limit=limit)

            result = []
            for o in orders:
                result.append({
                    "order_id": str(o["orderId"]),
                    "symbol": o["symbol"],
                    "status": o["status"],
                    "side": o["side"],
                    "type": o["type"],
                    "quantity": float(o["origQty"]),
                    "executed_qty": float(o["executedQty"]),
                    "avg_price": float(o["avgPrice"]) if o["avgPrice"] != "0" else 0.0,
                    "timestamp": datetime.fromtimestamp(o["time"] / 1000, tz=timezone.utc)
                })

            logger.debug(f"Fetched {len(result)} order(s)")
            return result
        except Exception as e:
            logger.error(f"Error fetching orders: {e}", exc_info=True)
            return []
