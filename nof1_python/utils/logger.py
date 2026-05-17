"""
Logger configuration module.
Configures loguru for application logging.
Also intercepts standard library logging to loguru.
"""
import sys
import logging
from loguru import logger
from pathlib import Path
from config.config import settings


class InterceptHandler(logging.Handler):
    """Intercept standard library logging and forward to loguru."""

    def emit(self, record):
        # Get corresponding loguru level
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Find caller depth
        frame, depth = logging.currentframe(), 2
        while frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


def setup_logger():
    """
    Setup loguru logger with console and file output.
    """
    # Remove default handler
    logger.remove()
    
    # Create logs directory if it doesn't exist
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # Console handler
    logger.add(
        sys.stdout,
        level=settings.LOG_LEVEL,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        colorize=True
    )
    
    # File handler - rotated daily
    logger.add(
        "logs/trading_bot_{time:YYYY-MM-DD}.log",
        rotation="00:00",
        retention="30 days",
        level=settings.LOG_LEVEL,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        encoding="utf-8"
    )
    
    # Intercept standard library logging (scheduler, agent, etc.)
    logging.basicConfig(
        handlers=[InterceptHandler()],
        level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
        force=True
    )
    # Also intercept existing loggers
    for name in logging.root.manager.loggerDict:
        _logger = logging.getLogger(name)
        _logger.handlers = [InterceptHandler()]
        _logger.propagate = False

    return logger


# Initialize logger
setup_logger()
