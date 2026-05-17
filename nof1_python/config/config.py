"""
Configuration management module.
Loads environment variables from .env file using pydantic-settings.
"""
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Exchange configuration
    BINANCE_API_KEY: str = ""
    BINANCE_API_SECRET: str = ""
    BINANCE_TESTNET: bool = True

    # LLM configuration
    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    AI_MODEL_NAME: str = "gpt-4"

    # Trading configuration
    TRADING_SYMBOL: str = "BTCUSDT"
    TRADING_INTERVAL_MINUTES: int = 60

    # Risk management configuration
    MAX_POSITION_SIZE: float = 0.1
    MAX_POSITIONS: int = 3
    STOP_LOSS_PERCENTAGE: float = 5.0
    TAKE_PROFIT_PERCENTAGE: float = 10.0
    TRADING_COOLDOWN_SECONDS: int = 300

    # Risk parameters for System Prompt
    EXTREME_STOP_LOSS_PERCENT: int = 5
    MAX_HOLDING_HOURS: int = 24
    MAX_LEVERAGE: int = 25

    # Database configuration
    DATABASE_URL: str = "mysql+pymysql://root:@127.0.0.1:3306/btc_quant"

    # Proxy configuration (for requests / python-binance)
    HTTP_PROXY: Optional[str] = None
    HTTPS_PROXY: Optional[str] = None
    PROXY_ENABLED: bool = True

    # Log configuration
    LOG_LEVEL: str = "INFO"

    # Strategy configuration
    STRATEGY: str = "ai-autonomous"
    ENABLE_CODE_LEVEL_PROTECTION: bool = True

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# Global settings instance
settings = Settings()
