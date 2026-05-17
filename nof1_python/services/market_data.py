"""
Market data service module.
Encapsulates python-binance to fetch K-lines, ticker, funding rate.
"""
from binance.client import Client
from typing import List, Dict, Optional
from datetime import datetime, timezone
import logging
import time

from config.config import settings
from utils.time_utils import get_utc_now

logger = logging.getLogger(__name__)


class MarketDataService:
    """Service for fetching market data from Binance Futures."""

    def __init__(self):
        """Initialize Binance client."""
        from binance.client import Client as _Client

        # python-binance 的 Client.__init__ 会调用 self.ping()，
        # ping 会访问 spot API（api.binance.com 或 testnet.binance.vision），
        # 在国内均不可达，导致 SSL 错误。
        # 解决方式：monkey-patch ping() 为空操作，初始化后再手动设置 URL。
        _Client.ping = lambda self: None

        # 代理配置
        proxy = getattr(settings, 'HTTP_PROXY', None) or getattr(settings, 'HTTPS_PROXY', None)
        requests_params = {'timeout': 60, 'verify': False}
        if proxy:
            requests_params['proxies'] = {'http': proxy, 'https': proxy}

        self.client = _Client(
            api_key=settings.BINANCE_API_KEY,
            api_secret=settings.BINANCE_API_SECRET,
            testnet=False,               # ping 已被 patch，这里设 False 即可
            requests_params=requests_params
        )

        # 恢复原始 ping（可选，保留原始行为）
        # _Client.ping = original_ping  # 如果需要可以恢复

        # 根据配置手动设置 testnet URL
        if settings.BINANCE_TESTNET:
            self.client.API_URL = 'https://testnet.binance.vision/api'
            self.client.FUTURES_URL = 'https://testnet.binancefuture.com/fapi'

        # 确保 session 代理生效（双重保险）
        if proxy:
            self.client.session.proxies = {'http': proxy, 'https': proxy}
        # 禁用 SSL 验证（Clash 代理对 testnet.binancefuture.com SSL 握手有问题）
        self.client.session.verify = False

        # 增大 recvWindow 到 60 秒，避免 -1021 时间戳错误
        self.client.recvWindow = 60000

        # 同步服务器时间戳偏移（避免 -1021 错误）
        try:
            from utils.time_utils import get_binance_timestamp_offset
            proxy = getattr(settings, 'HTTP_PROXY', None) or getattr(settings, 'HTTPS_PROXY', None)
            offset = get_binance_timestamp_offset(proxy_url=proxy, verify_ssl=False)
            self.client.timestamp_offset = offset
        except Exception as e:
            logger.warning(f"Could not sync timestamp: {e}")
            self.client.timestamp_offset = 0

        logger.info(f"MarketDataService initialized (testnet={settings.BINANCE_TESTNET})")

    def get_klines(
        self,
        symbol: str = None,
        interval: str = "1h",
        limit: int = 100
    ) -> List[Dict]:
        """
        Get K-line (candlestick) data for a symbol.

        Args:
            symbol: Trading pair (default from settings)
            interval: Timeframe (1m, 5m, 15m, 1h, 4h, etc.)
            limit: Number of candles (max 1000)

        Returns:
            List[Dict]: List of kline data
        """
        if symbol is None:
            symbol = settings.TRADING_SYMBOL

        # LLM 可能返回不完整的 symbol（如 'BTC' 而不是 'BTCUSDT'）
        if symbol and not symbol.endswith('USDT') and not symbol.endswith('USDC'):
            fixed = symbol + 'USDT'
            logger.info(f"symbol 不完整，自动修正: {symbol!r} -> {fixed!r}")
            symbol = fixed

        logger.info(f"get_klines: symbol={symbol}, interval={interval}, limit={limit}")
        
        try:
            klines = self.client.futures_klines(
                symbol=symbol,
                interval=interval,
                limit=limit
            )

            result = []
            for k in klines:
                result.append({
                    "timestamp": datetime.fromtimestamp(k[0] / 1000, tz=timezone.utc),
                    "open": float(k[1]),
                    "high": float(k[2]),
                    "low": float(k[3]),
                    "close": float(k[4]),
                    "volume": float(k[5]),
                    "close_time": datetime.fromtimestamp(k[6] / 1000, tz=timezone.utc),
                    "quote_volume": float(k[7]),
                    "trades": int(k[8]),
                    "taker_buy_base": float(k[9]),
                    "taker_buy_quote": float(k[10])
                })

            logger.debug(f"Fetched {len(result)} klines for {symbol} {interval}")
            return result

        except Exception as e:
            logger.error(f"Error fetching klines: {e}")
            raise

    def get_multi_timeframe_klines(
        self,
        symbol: str = None,
        timeframes: List[str] = None,
        limit: int = 100
    ) -> Dict[str, List[Dict]]:
        """
        Get K-line data for multiple timeframes.

        Args:
            symbol: Trading pair
            timeframes: List of timeframes (e.g., ["5m", "15m", "1h", "4h"])
            limit: Number of candles per timeframe

        Returns:
            Dict[str, List[Dict]]: Kline data per timeframe
        """
        if symbol is None:
            symbol = settings.TRADING_SYMBOL
        if timeframes is None:
            timeframes = ["5m", "15m", "1h", "4h"]

        result = {}
        for tf in timeframes:
            result[tf] = self.get_klines(symbol, tf, limit)

        return result

    def get_ticker(self, symbol: str = None) -> Dict:
        """
        Get 24hr ticker price change statistics.

        Args:
            symbol: Trading pair

        Returns:
            Dict: Ticker data
        """
        if symbol is None:
            symbol = settings.TRADING_SYMBOL
        # LLM 可能返回不完整的 symbol
        if symbol and not symbol.endswith('USDT') and not symbol.endswith('USDC'):
            fixed = symbol + 'USDT'
            logger.info(f"symbol 不完整，自动修正: {symbol!r} -> {fixed!r}")
            symbol = fixed

        try:
            # 直接通过 session 调用 futures ticker/24hr，
            # 避免 _request() 的 version 参数传递问题。
            base = self.client.FUTURES_URL
            url = f"{base}/v1/ticker/24hr?symbol={symbol}"
            resp = self.client.session.get(url)
            resp.raise_for_status()
            ticker_data = resp.json()
            logger.debug(f"Fetched ticker for {symbol}: price={ticker_data.get('lastPrice')}")
            return {
                "symbol": ticker_data["symbol"],
                "price": float(ticker_data["lastPrice"]),
                "price_change": float(ticker_data["priceChange"]),
                "price_change_percent": float(ticker_data["priceChangePercent"]),
                "volume": float(ticker_data["volume"]),
                "quote_volume": float(ticker_data["quoteVolume"]),
                "high": float(ticker_data["highPrice"]),
                "low": float(ticker_data["lowPrice"]),
                "timestamp": datetime.now(timezone.utc)
            }
        except Exception as e:
            logger.error(f"Error fetching ticker: {e}")
            raise

    def get_current_price(self, symbol: str = None) -> float:
        """
        Get current market price for a symbol.

        Args:
            symbol: Trading pair (e.g., "BTC", "ETH")

        Returns:
            float: Current price
        """
        if symbol is None:
            symbol = settings.TRADING_SYMBOL
        elif not symbol.endswith("USDT"):
            symbol = f"{symbol}USDT"

        try:
            ticker = self.client.futures_symbol_ticker(symbol=symbol)
            price = float(ticker["price"])
            logger.debug(f"Current price for {symbol}: {price}")
            return price
        except Exception as e:
            logger.error(f"Error fetching price: {e}")
            raise

    def get_funding_rate(self, symbol: str = None) -> Dict:
        """
        Get funding rate for perpetual contracts.

        Args:
            symbol: Trading pair (e.g., "BTCUSDT")

        Returns:
            Dict: Funding rate data
        """
        if symbol is None:
            symbol = settings.TRADING_SYMBOL
        elif not symbol.endswith("USDT"):
            symbol = f"{symbol}USDT"

        try:
            funding_rate = self.client.futures_funding_rate(symbol=symbol, limit=1)
            if funding_rate:
                result = {
                    "symbol": funding_rate[0]["symbol"],
                    "funding_rate": float(funding_rate[0]["fundingRate"]),
                    "funding_time": datetime.fromtimestamp(
                        funding_rate[0]["fundingTime"] / 1000,
                        tz=timezone.utc
                    )
                }
                logger.debug(f"Funding rate for {symbol}: {result['funding_rate']}")
                return result
            return {"symbol": symbol, "funding_rate": 0.0, "funding_time": get_utc_now()}
        except Exception as e:
            logger.error(f"Error fetching funding rate: {e}")
            return {"symbol": symbol, "funding_rate": 0.0, "funding_time": get_utc_now()}

    def get_order_book(self, symbol: str = None, limit: int = 20) -> Dict:
        """
        Get order book (market depth).

        Args:
            symbol: Trading pair
            limit: Number of bid/ask levels (default 20)

        Returns:
            Dict: Order book with bids and asks
        """
        if symbol is None:
            symbol = settings.TRADING_SYMBOL
        # LLM 可能返回不完整的 symbol
        if symbol and not symbol.endswith('USDT') and not symbol.endswith('USDC'):
            fixed = symbol + 'USDT'
            logger.info(f"symbol 不完整，自动修正: {symbol!r} -> {fixed!r}")
            symbol = fixed

        try:
            depth = self.client.futures_order_book(symbol=symbol, limit=limit)
            result = {
                "symbol": symbol,
                "timestamp": get_utc_now(),
                "bids": [[float(price), float(qty)] for price, qty in depth["bids"]],
                "asks": [[float(price), float(qty)] for price, qty in depth["asks"]]
            }
            logger.debug(f"Fetched order book for {symbol} (limit={limit})")
            return result
        except Exception as e:
            logger.error(f"Error fetching order book: {e}")
            raise

    def get_technical_indicators(self, symbol: str, timeframes: List[str]) -> Dict:
        """
        Calculate technical indicators for given symbol and timeframes.
        This method fetches klines and calculates common indicators.

        Args:
            symbol: Trading pair
            timeframes: List of timeframes

        Returns:
            Dict: Technical indicators per timeframe
        """
        import pandas as pd
        import numpy as np

        result = {}
        klines_data = self.get_multi_timeframe_klines(symbol, timeframes, limit=100)

        for tf in timeframes:
            if tf not in klines_data or not klines_data[tf]:
                continue

            # Convert to DataFrame
            df = pd.DataFrame(klines_data[tf])

            # Calculate EMA
            ema20 = df["close"].ewm(span=20, adjust=False).mean().iloc[-1]
            ema50 = df["close"].ewm(span=50, adjust=False).mean().iloc[-1]

            # Calculate MACD
            ema12 = df["close"].ewm(span=12, adjust=False).mean()
            ema26 = df["close"].ewm(span=26, adjust=False).mean()
            macd_line = ema12 - ema26
            signal_line = macd_line.ewm(span=9, adjust=False).mean()
            macd_histogram = macd_line - signal_line

            # Calculate RSI
            def calculate_rsi(prices, period):
                delta = prices.diff()
                gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
                rs = gain / loss
                rsi = 100 - (100 / (1 + rs))
                return rsi.iloc[-1]

            rsi7 = calculate_rsi(df["close"], 7)
            rsi14 = calculate_rsi(df["close"], 14)

            result[tf] = {
                "timeframe": tf,
                "price": float(df["close"].iloc[-1]),
                "ema20": float(ema20),
                "ema50": float(ema50),
                "macd": float(macd_line.iloc[-1]),
                "macd_signal": float(signal_line.iloc[-1]),
                "macd_histogram": float(macd_histogram.iloc[-1]),
                "rsi7": float(rsi7),
                "rsi14": float(rsi14),
                "volume": float(df["volume"].iloc[-1]),
                "trend": "bullish" if df["close"].iloc[-1] > ema20 else "bearish"
            }

        return result
