"""
Main entry point for the nof1.ai clone trading bot.
Initializes all components and starts the trading loop.
"""
import os
from dotenv import load_dotenv

# 在一切之前加载 .env 并设置代理到 os.environ
# 这样 python-binance / requests 自动走代理，不需要手动设置环境变量
load_dotenv()
_proxy = os.getenv('HTTP_PROXY', '')
if _proxy:
    os.environ['HTTP_PROXY'] = _proxy
    os.environ['HTTPS_PROXY'] = os.getenv('HTTPS_PROXY', _proxy)
    # 同时设置小写（某些库读小写）
    os.environ['http_proxy'] = _proxy
    os.environ['https_proxy'] = os.getenv('HTTPS_PROXY', _proxy)
    # testnet.binancefuture.com 国内直连可访问，绕过 Clash 代理
    # 同时确保本地地址（LM Studio 127.0.0.1:1234）不走代理
    for _var in ('NO_PROXY', 'no_proxy'):
        _existing = os.environ.get(_var, '')
        _entries = [e.strip() for e in _existing.split(',') if e.strip()]
        _needed = ['localhost', '127.0.0.1', 'testnet.binancefuture.com']
        for _item in _needed:
            if _item not in _entries:
                _entries.append(_item)
        os.environ[_var] = ','.join(_entries)

# 禁用 SSL 验证警告（通过 Clash 代理访问 binance 时经常出现）
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

import logging
# 让标准 logging 模块也输出到终端（trading_agent.py 使用标准 logging）
logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)-8s | %(message)s')
from pathlib import Path

from utils.logger import setup_logger
from config.config import settings
from database.database import init_database
from scheduler.trading_loop import TradingScheduler, setup_signal_handlers
import sys


def main():
    """Main function to start the trading bot."""
    # Setup logger
    logger = setup_logger()
    
    logger.info("=" * 60)
    logger.info("nof1.ai Clone - Crypto Trading Bot")
    logger.info("=" * 60)
    
    # Print configuration
    logger.info("Configuration:")
    logger.info(f"  - Trading Symbols: {settings.TRADING_SYMBOLS}")
    logger.info(f"  - Trading Interval: {settings.TRADING_INTERVAL_MINUTES} minutes")
    logger.info(f"  - Strategy: {settings.STRATEGY}")
    logger.info(f"  - AI Model: {settings.AI_MODEL_NAME}")
    logger.info(f"  - Binance Testnet: {settings.BINANCE_TESTNET}")
    logger.info(f"  - Max Positions: {settings.MAX_POSITIONS}")
    logger.info(f"  - Max Leverage: {settings.MAX_LEVERAGE}x")
    logger.info("=" * 60)
    
    # Validate configuration
    if not settings.OPENAI_API_KEY:
        logger.error("OPENAI_API_KEY is not set! Please configure .env file.")
        sys.exit(1)
    
    if not settings.BINANCE_API_KEY or not settings.BINANCE_API_SECRET:
        logger.warning(
            "Binance API credentials not set. "
            "Some features may not work."
        )
    
    # Initialize database
    logger.info("Initializing database...")
    try:
        init_database()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        sys.exit(1)
    
    # Create logs directory
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)
    
    # Initialize and start trading scheduler
    logger.info("Initializing trading scheduler...")
    try:
        scheduler = TradingScheduler()
        
        # Setup signal handlers for graceful shutdown
        setup_signal_handlers(scheduler)
        
        # Start scheduler
        scheduler.start()
        
        logger.info("Trading bot is now running. Press Ctrl+C to stop.")
        
        # Keep main thread alive
        import time
        while True:
            time.sleep(1)
        
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received...")
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
    finally:
        logger.info("Shutting down...")
        if 'scheduler' in locals():
            scheduler.stop()
        logger.info("Trading bot stopped successfully")


if __name__ == "__main__":
    main()
