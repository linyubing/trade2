"""
Time utilities module.
Provides UTC time functions for consistent timestamp handling.
"""
from datetime import datetime, timezone
import time
import logging
import requests

logger = logging.getLogger(__name__)


def get_binance_timestamp_offset(proxy_url=None, verify_ssl=False):
    """
    Get timestamp offset from Binance server.
    Uses testnet.binance.vision / api.binance.com which are accessible via proxy from China.
    Returns offset in ms (server_time - local_time).
    Negative = local clock is ahead of server.
    """
    urls = [
        'https://testnet.binance.vision/api/v3/time',
        'https://api.binance.com/api/v3/time',
    ]
    proxies = {'http': proxy_url, 'https': proxy_url} if proxy_url else None
    for url in urls:
        try:
            r = requests.get(url, proxies=proxies, timeout=10, verify=verify_ssl)
            if r.status_code == 200:
                server_time = r.json()['serverTime']
                local_time = int(time.time() * 1000)
                offset = server_time - local_time
                logger.info(f"Binance time sync: server={server_time}, local={local_time}, offset={offset}ms")
                return offset
        except Exception as e:
            logger.warning(f"Failed to sync time from {url}: {e}")
            continue
    logger.warning("Could not sync time with Binance, using offset=0")
    return 0


def get_utc_now() -> datetime:
    """
    Get current UTC time as datetime object.
    
    Returns:
        datetime: Current UTC time
    """
    return datetime.now(timezone.utc)


def get_utc_timestamp() -> str:
    """
    Get current UTC time as ISO format string.
    
    Returns:
        str: UTC timestamp in ISO format
    """
    return get_utc_now().isoformat()


def format_utc_time(dt: datetime, fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    """
    Format datetime to string in UTC.
    
    Args:
        dt: Datetime object (assumed to be UTC)
        fmt: Format string
        
    Returns:
        str: Formatted time string
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.strftime(fmt)


def parse_iso_time(time_str: str) -> datetime:
    """
    Parse ISO format time string to datetime.
    
    Args:
        time_str: ISO format time string
        
    Returns:
        datetime: Parsed datetime object in UTC
    """
    return datetime.fromisoformat(time_str.replace("Z", "+00:00"))


def get_minutes_elapsed(start_time: datetime) -> float:
    """
    Calculate minutes elapsed since start_time.
    
    Args:
        start_time: Start time (UTC)
        
    Returns:
        float: Minutes elapsed
    """
    elapsed = datetime.now(timezone.utc) - start_time
    return elapsed.total_seconds() / 60
