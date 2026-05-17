"""
快速测试 MarketDataService，诊断 Invalid symbol 错误。
"""
import os
import sys
from dotenv import load_dotenv

load_dotenv()

_proxy = os.getenv('HTTP_PROXY', '')
if _proxy:
    os.environ['HTTP_PROXY'] = _proxy
    os.environ['HTTPS_PROXY'] = os.getenv('HTTPS_PROXY', _proxy)
    os.environ['http_proxy'] = _proxy
    os.environ['https_proxy'] = os.getenv('HTTPS_PROXY', _proxy)

from config.config import settings
from services.market_data import MarketDataService

print(f"TRADING_SYMBOL = {settings.TRADING_SYMBOL!r}")
print(f"BINANCE_TESTNET = {settings.BINANCE_TESTNET}")
print(f"HTTP_PROXY = {settings.HTTP_PROXY}")

try:
    svc = MarketDataService()
    print(f"client.API_URL = {svc.client.API_URL}")
    print(f"client.FUTURES_URL = {svc.client.FUTURES_URL}")
    print(f"client.testnet = {svc.client.testnet}")

    # 直接测试 futures_klines
    print("\n--- 测试 futures_klines ---")
    klines = svc.client.futures_klines(symbol="BTCUSDT", interval="1h", limit=3)
    print(f"成功！获取到 {len(klines)} 条K线")
    print(f"最新收盘价: {klines[-1][4]}")

    # 测试 get_klines 方法
    print("\n--- 测试 get_klines 方法 ---")
    result = svc.get_klines(symbol="BTCUSDT", interval="1h", limit=3)
    print(f"成功！获取到 {len(result)} 条K线")

except Exception as e:
    print(f"错误: {e}")
    import traceback
    traceback.print_exc()
finally:
    input("\n按回车退出...")
