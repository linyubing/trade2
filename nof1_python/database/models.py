"""
Database models module.
Defines SQLAlchemy ORM models for all tables.
Uses MySQL syntax as specified in PRD Section 6.1.
"""
from sqlalchemy import (
    Column, Integer, String, DateTime, DECIMAL, Text, 
    Index, UniqueConstraint
)
from sqlalchemy.sql import func
from sqlalchemy.orm import declarative_base
import logging

logger = logging.getLogger(__name__)

Base = declarative_base()


class AccountSnapshot(Base):
    """Account snapshots table - records account status at each snapshot."""
    __tablename__ = 'account_snapshots'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=func.now())
    balance = Column(DECIMAL(18, 8), nullable=True)  # USDT balance
    equity = Column(DECIMAL(18, 8), nullable=True)   # Net equity
    available_balance = Column(DECIMAL(18, 8), nullable=True)  # Available balance
    unrealized_pnl = Column(DECIMAL(18, 8), nullable=True)  # Unrealized PnL
    
    __table_args__ = (
        Index('idx_account_snapshots_timestamp', 'timestamp'),
    )


class Position(Base):
    """Positions table - records current positions."""
    __tablename__ = 'positions'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(20), nullable=False, index=True)
    side = Column(String(10), nullable=False)  # long or short
    quantity = Column(DECIMAL(18, 8), nullable=False)
    entry_price = Column(DECIMAL(18, 8), nullable=False)
    unrealized_pnl = Column(DECIMAL(18, 8), nullable=True)
    leverage = Column(Integer, nullable=True)
    open_time = Column(DateTime, default=func.now())
    status = Column(String(20), default='OPEN')  # OPEN or CLOSED
    close_time = Column(DateTime, nullable=True)
    realized_pnl = Column(DECIMAL(18, 8), nullable=True)
    
    __table_args__ = (
        Index('idx_positions_symbol', 'symbol'),
        Index('idx_positions_status', 'status'),
    )


class Trade(Base):
    """Trades table - records every trade execution."""
    __tablename__ = 'trades'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=func.now())
    symbol = Column(String(20), nullable=False, index=True)
    side = Column(String(10), nullable=False)  # BUY or SELL
    quantity = Column(DECIMAL(18, 8), nullable=False)
    price = Column(DECIMAL(18, 8), nullable=False)
    order_id = Column(String(100), nullable=True)
    pnl = Column(DECIMAL(18, 8), nullable=True)  # Realized PnL
    status = Column(String(20), default='FILLED')  # NEW, FILLED, CANCELED
    commission = Column(DECIMAL(18, 8), nullable=True)
    commission_asset = Column(String(10), nullable=True)
    trade_type = Column(String(20), nullable=True)  # OPEN or CLOSE
    
    __table_args__ = (
        Index('idx_trades_timestamp', 'timestamp'),
        Index('idx_trades_symbol', 'symbol'),
    )


class AIDecision(Base):
    """AI decisions table - records each AI decision for audit."""
    __tablename__ = 'ai_decisions'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=func.now())
    prompt = Column(Text, nullable=False)  # Input prompt to LLM
    response = Column(Text, nullable=False)  # Raw LLM response
    decision = Column(Text, nullable=False)  # Parsed decision (JSON)
    execution_result = Column(Text, nullable=True)  # Execution result (JSON)
    model_name = Column(String(100), nullable=False)
    iteration = Column(Integer, nullable=True)  # Trading cycle number
    
    __table_args__ = (
        Index('idx_ai_decisions_timestamp', 'timestamp'),
        Index('idx_ai_decisions_model', 'model_name'),
    )


class MarketData(Base):
    """Market data table - caches market data for analysis."""
    __tablename__ = 'market_data'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(20), nullable=False, index=True)
    interval = Column(String(10), nullable=False, index=True)  # 5m/15m/1h/4h
    timestamp = Column(DateTime, nullable=False, index=True)
    open = Column(DECIMAL(18, 8), nullable=False)
    high = Column(DECIMAL(18, 8), nullable=False)
    low = Column(DECIMAL(18, 8), nullable=False)
    close = Column(DECIMAL(18, 8), nullable=False)
    volume = Column(DECIMAL(18, 8), nullable=False)
    
    __table_args__ = (
        UniqueConstraint('symbol', 'interval', 'timestamp', name='uq_market_data_symbol_interval_timestamp'),
        Index('idx_market_data_symbol_interval', 'symbol', 'interval'),
    )


logger.info("Database models defined successfully")
