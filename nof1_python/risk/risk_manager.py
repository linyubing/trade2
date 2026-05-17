"""
Risk management module.
Implements stop-loss checks, max position limits, and trading cooldown.
"""
from typing import Dict, List, Optional
from datetime import datetime, timezone, timedelta
import logging

from config.config import settings
from utils.time_utils import get_utc_now

logger = logging.getLogger(__name__)


class RiskManager:
    """Risk management service for trading operations."""
    
    def __init__(self):
        """Initialize Risk Manager."""
        self.last_trade_time = None
        self.stop_loss_checks = {}  # symbol -> last check time
        logger.info("RiskManager initialized")
    
    def check_stop_loss(self, positions: List[Dict]) -> List[Dict]:
        """
        Check all positions for stop-loss triggers.
        
        Args:
            positions: List of current positions
            
        Returns:
            List[Dict]: List of positions that triggered stop-loss
        """
        triggered = []
        
        for pos in positions:
            symbol = pos.get("symbol")
            side = pos.get("side")
            entry_price = pos.get("entry_price", 0)
            current_price = pos.get("mark_price", pos.get("current_price", 0))
            leverage = pos.get("leverage", 1)
            
            # Determine stop-loss percentage based on leverage
            if leverage <= 5:
                stop_loss_pct = 0.08  # 8%
            elif leverage <= 15:
                stop_loss_pct = 0.06  # 6%
            else:
                stop_loss_pct = 0.05  # 5%
            
            # Calculate stop-loss price
            if side == "long":
                stop_loss_price = entry_price * (1 - stop_loss_pct)
                triggered_stop = current_price <= stop_loss_price
            else:  # short
                stop_loss_price = entry_price * (1 + stop_loss_pct)
                triggered_stop = current_price >= stop_loss_price
            
            if triggered_stop:
                logger.warning(
                    f"Stop-loss triggered for {symbol} {side}: "
                    f"entry={entry_price:.2f}, current={current_price:.2f}, "
                    f"stop={stop_loss_price:.2f}"
                )
                triggered.append({
                    "symbol": symbol,
                    "side": side,
                    "action": "close_position",
                    "reason": "stop_loss",
                    "entry_price": entry_price,
                    "current_price": current_price,
                    "stop_loss_price": stop_loss_price,
                    "unrealized_pnl": pos.get("unrealized_pnl", 0)
                })
            
            # Check extreme stop-loss (hard limit)
            extreme_stop_pct = settings.EXTREME_STOP_LOSS_PERCENT / 100
            if side == "long":
                extreme_price = entry_price * (1 - extreme_stop_pct)
                if current_price <= extreme_price:
                    logger.error(f"EXTREME stop-loss triggered for {symbol}")
                    triggered.append({
                        "symbol": symbol,
                        "side": side,
                        "action": "force_close",
                        "reason": "extreme_stop_loss",
                        "entry_price": entry_price,
                        "current_price": current_price
                    })
            else:
                extreme_price = entry_price * (1 + extreme_stop_pct)
                if current_price >= extreme_price:
                    logger.error(f"EXTREME stop-loss triggered for {symbol}")
                    triggered.append({
                        "symbol": symbol,
                        "side": side,
                        "action": "force_close",
                        "reason": "extreme_stop_loss",
                        "entry_price": entry_price,
                        "current_price": current_price
                    })
        
        return triggered
    
    def check_take_profit(self, positions: List[Dict]) -> List[Dict]:
        """
        Check positions for take-profit triggers (batch closing).
        
        Args:
            positions: List of current positions
            
        Returns:
            List[Dict]: List of partial close actions
        """
        actions = []
        
        for pos in positions:
            entry_price = pos.get("entry_price", 0)
            current_price = pos.get("mark_price", pos.get("current_price", 0))
            side = pos.get("side")
            unrealized_pnl = pos.get("unrealized_pnl", 0)
            entry_value = entry_price * pos.get("quantity", 0)
            
            if entry_value == 0:
                continue
            
            # Calculate profit percentage
            if side == "long":
                profit_pct = (current_price - entry_price) / entry_price * 100
            else:
                profit_pct = (entry_price - current_price) / entry_price * 100
            
            # Add leverage effect
            leverage = pos.get("leverage", 1)
            profit_pct *= leverage
            
            # Check batch take-profit levels
            if profit_pct >= 18:
                # Close 40%
                actions.append({
                    "symbol": pos["symbol"],
                    "action": "partial_close",
                    "close_percent": 40,
                    "reason": "take_profit_18%"
                })
            elif profit_pct >= 12:
                # Close 30%
                actions.append({
                    "symbol": pos["symbol"],
                    "action": "partial_close",
                    "close_percent": 30,
                    "reason": "take_profit_12%"
                })
            elif profit_pct >= 8:
                # Close 30%
                actions.append({
                    "symbol": pos["symbol"],
                    "action": "partial_close",
                    "close_percent": 30,
                    "reason": "take_profit_8%"
                })
        
        return actions
    
    def check_position_limit(self, symbol: str, current_positions: List[Dict]) -> bool:
        """
        Check if position limit is exceeded.
        
        Args:
            symbol: Trading symbol
            current_positions: List of current positions
            
        Returns:
            bool: True if can open new position, False if limit exceeded
        """
        # Count positions for this symbol
        symbol_positions = [p for p in current_positions if p.get("symbol") == symbol]
        total_positions = len(current_positions)
        
        if total_positions >= settings.MAX_POSITIONS:
            logger.warning(
                f"Position limit reached: {total_positions}/{settings.MAX_POSITIONS}"
            )
            return False
        
        logger.debug(
            f"Position check passed: {total_positions}/{settings.MAX_POSITIONS}"
        )
        return True
    
    def check_trading_cooldown(self) -> bool:
        """
        Check if trading cooldown period has passed.
        
        Returns:
            bool: True if can trade, False if in cooldown
        """
        if self.last_trade_time is None:
            return True
        
        elapsed = get_utc_now() - self.last_trade_time
        cooldown = timedelta(seconds=settings.TRADING_COOLDOWN_SECONDS)
        
        if elapsed < cooldown:
            remaining = (cooldown - elapsed).total_seconds()
            logger.debug(f"Trading cooldown active: {remaining:.0f}s remaining")
            return False
        
        return True
    
    def check_leverage_limit(self, leverage: int) -> bool:
        """
        Check if leverage is within allowed limits.
        
        Args:
            leverage: Requested leverage
            
        Returns:
            bool: True if allowed, False otherwise
        """
        if leverage > settings.MAX_LEVERAGE:
            logger.warning(
                f"Leverage {leverage}x exceeds maximum {settings.MAX_LEVERAGE}x"
            )
            return False
        return True
    
    def check_max_holding_time(self, positions: List[Dict]) -> List[Dict]:
        """
        Check if any position has exceeded max holding time.
        
        Args:
            positions: List of current positions
            
        Returns:
            List[Dict]: List of positions to force close
        """
        actions = []
        now = get_utc_now()
        max_hours = settings.MAX_HOLDING_HOURS
        
        for pos in positions:
            open_time = pos.get("open_time")
            if isinstance(open_time, str):
                open_time = datetime.fromisoformat(open_time.replace("Z", "+00:00"))
            
            if open_time:
                holding_time = (now - open_time).total_seconds() / 3600
                if holding_time > max_hours:
                    logger.warning(
                        f"Position {pos['symbol']} exceeded max holding time: "
                        f"{holding_time:.1f}h > {max_hours}h"
                    )
                    actions.append({
                        "symbol": pos["symbol"],
                        "action": "force_close",
                        "reason": "max_holding_time_exceeded",
                        "holding_hours": holding_time
                    })
        
        return actions
    
    def calculate_risk(
        self, 
        symbol: str, 
        side: str, 
        leverage: int, 
        amount_usdt: float,
        stop_loss_percent: float = None
    ) -> Dict:
        """
        Calculate risk metrics for a proposed trade.
        
        Args:
            symbol: Trading symbol
            side: Trade side (long/short)
            leverage: Leverage multiplier
            amount_usdt: Margin amount in USDT
            stop_loss_percent: Stop-loss percentage (optional)
            
        Returns:
            Dict: Risk metrics
        """
        # Get current price
        from services.market_data import MarketDataService
        market_service = MarketDataService()
        current_price = market_service.get_current_price(symbol)
        
        # Calculate position size
        position_value = amount_usdt * leverage
        quantity = position_value / current_price
        
        # Default stop-loss based on leverage
        if stop_loss_percent is None:
            if leverage <= 5:
                stop_loss_percent = 8.0
            elif leverage <= 15:
                stop_loss_percent = 6.0
            else:
                stop_loss_percent = 5.0
        
        # Calculate liquidation price (simplified)
        # In reality, this depends on Binance's specific formula
        if side == "long":
            liquidation_price = current_price * (1 - 0.8 / leverage)  # Rough estimate
            stop_loss_price = current_price * (1 - stop_loss_percent / 100)
        else:
            liquidation_price = current_price * (1 + 0.8 / leverage)
            stop_loss_price = current_price * (1 + stop_loss_percent / 100)
        
        # Calculate max loss
        max_loss = amount_usdt * (stop_loss_percent / 100)
        
        # Check risk limits
        risk_check = {
            "allowed": True,
            "warnings": []
        }
        
        if leverage > settings.MAX_LEVERAGE:
            risk_check["allowed"] = False
            risk_check["warnings"].append(
                f"Leverage {leverage}x exceeds maximum {settings.MAX_LEVERAGE}x"
            )
        
        if max_loss > amount_usdt * 0.1:  # More than 10% of margin
            risk_check["warnings"].append(
                f"Potential loss ({max_loss:.2f} USDT) exceeds 10% of margin"
            )
        
        return {
            "symbol": symbol,
            "side": side,
            "leverage": leverage,
            "amount_usdt": amount_usdt,
            "current_price": current_price,
            "position_value": position_value,
            "quantity": quantity,
            "stop_loss_percent": stop_loss_percent,
            "stop_loss_price": stop_loss_price,
            "liquidation_price": liquidation_price,
            "max_loss_usdt": max_loss,
            "risk_check": risk_check
        }
    
    def check_before_trade(
        self, 
        symbol: str, 
        side: str, 
        leverage: int, 
        amount_usdt: float
    ) -> Dict:
        """
        Comprehensive risk check before placing a trade.
        
        Args:
            symbol: Trading symbol
            side: Trade side
            leverage: Leverage multiplier
            amount_usdt: Margin amount
            
        Returns:
            Dict: Check result with 'allowed' flag
        """
        # This would need access to current positions
        # For now, return a basic check
        result = {
            "allowed": True,
            "reason": ""
        }
        
        # Check leverage limit
        if not self.check_leverage_limit(leverage):
            result["allowed"] = False
            result["reason"] = f"Leverage {leverage}x exceeds maximum"
            return result
        
        # Check trading cooldown
        if not self.check_trading_cooldown():
            result["allowed"] = False
            result["reason"] = "Trading cooldown active"
            return result
        
        return result
    
    def update_last_trade_time(self):
        """Update last trade time (for cooldown tracking)."""
        self.last_trade_time = get_utc_now()
    
    def check_trailing_stop(self, positions: List[Dict]) -> List[Dict]:
        """
        Check and update trailing stop for profitable positions.
        
        Args:
            positions: List of current positions
            
        Returns:
            List[Dict]: List of trailing stop update actions
        """
        actions = []
        
        for pos in positions:
            unrealized_pnl = pos.get("unrealized_pnl", 0)
            entry_price = pos.get("entry_price", 0)
            current_price = pos.get("mark_price", pos.get("current_price", 0))
            
            if entry_price == 0:
                continue
            
            # Calculate profit percentage
            side = pos.get("side")
            if side == "long":
                profit_pct = (current_price - entry_price) / entry_price * 100
            else:
                profit_pct = (entry_price - current_price) / entry_price * 100
            
            leverage = pos.get("leverage", 1)
            profit_pct *= leverage
            
            # Check trailing stop triggers
            # Profit 5% → move stop to +2%
            # Profit 10% → move stop to +5%
            # Profit 15% → move stop to +8%
            new_stop_pct = None
            if profit_pct >= 15:
                new_stop_pct = 8
            elif profit_pct >= 10:
                new_stop_pct = 5
            elif profit_pct >= 5:
                new_stop_pct = 2
            
            if new_stop_pct is not None:
                actions.append({
                    "symbol": pos["symbol"],
                    "action": "update_trailing_stop",
                    "profit_pct": profit_pct,
                    "new_stop_pct": new_stop_pct,
                    "message": f"Trailing stop updated to +{new_stop_pct}%"
                })
        
        return actions
