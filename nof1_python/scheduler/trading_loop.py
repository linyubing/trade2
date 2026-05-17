"""
Trading loop scheduler module.
Uses APScheduler for periodic trading cycles.
"""
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED
import logging
import signal
import sys

from config.config import settings
from agent.trading_agent import TradingAgent
from risk.risk_manager import RiskManager
from services.account_manager import AccountManager
from utils.logger import setup_logger

logger = logging.getLogger(__name__)


class TradingScheduler:
    """Main trading loop scheduler."""
    
    def __init__(self):
        """Initialize the trading scheduler."""
        self.scheduler = BackgroundScheduler()
        self.trading_agent = TradingAgent()
        self.risk_manager = RiskManager()
        self.account_manager = AccountManager()
        self.is_running = False
        
        # Register event listeners
        self.scheduler.add_listener(
            self._job_executed, 
            EVENT_JOB_EXECUTED
        )
        self.scheduler.add_listener(
            self._job_error, 
            EVENT_JOB_ERROR
        )
        
        logger.info("TradingScheduler initialized")
    
    def start(self):
        """Start the trading scheduler."""
        if self.is_running:
            logger.warning("Scheduler is already running")
            return
        
        symbols = settings.TRADING_SYMBOLS
        logger.info(
            f"Starting trading scheduler "
            f"(interval={settings.TRADING_INTERVAL_MINUTES} minutes, "
            f"symbols={symbols})"
        )
        
        # Add trading job for each symbol
        trigger = IntervalTrigger(
            minutes=settings.TRADING_INTERVAL_MINUTES
        )
        for symbol in symbols:
            job_id = f"trading_cycle_{symbol}"
            self.scheduler.add_job(
                func=self._trading_cycle_wrapper,
                trigger=trigger,
                args=[symbol],
                id=job_id,
                name=f"Trading Cycle - {symbol}",
                replace_existing=True
            )
            logger.info(f"Added trading job for {symbol} (id={job_id})")
        
        # Add risk management job (runs for all symbols)
        self.scheduler.add_job(
            func=self._check_risk_management,
            trigger=trigger,
            id="risk_management_check",
            name="Risk Management Check",
            replace_existing=True
        )
        
        # Start scheduler
        self.scheduler.start()
        self.is_running = True
        
        logger.info("Trading scheduler started successfully")
        
        # Run first cycle immediately for each symbol (staggered to avoid proxy overload)
        logger.info("Running initial trading cycles...")
        import time
        self._check_risk_management()
        for i, symbol in enumerate(symbols):
            logger.info(f"Running initial cycle for {symbol}...")
            self._trading_cycle_wrapper(symbol)
            if i < len(symbols) - 1:
                time.sleep(2)  # Stagger initial cycles by 2s to avoid proxy overload
    
    def stop(self):
        """Stop the trading scheduler gracefully."""
        if not self.is_running:
            logger.warning("Scheduler is not running")
            return
        
        logger.info("Stopping trading scheduler...")
        self.scheduler.shutdown(wait=True)
        self.is_running = False
        logger.info("Trading scheduler stopped successfully")
    
    def _trading_cycle_wrapper(self, symbol: str = None):
        """Wrapper for trading cycle with error handling.

        Args:
            symbol: Trading symbol for this cycle. Defaults to first symbol
                   in TRADING_SYMBOLS for backward compatibility.
        """
        if symbol is None:
            symbol = settings.TRADING_SYMBOLS[0] if settings.TRADING_SYMBOLS else "BTCUSDT"

        try:
            logger.info("=" * 60)
            logger.info(f"Starting new trading cycle for {symbol}")
            logger.info("=" * 60)
            
            # Run trading cycle for the specific symbol
            result = self.trading_agent.run_trading_cycle(symbol)
            
            logger.info(f"Trading cycle completed for {symbol}: {result}")
            
        except Exception as e:
            logger.error(f"Error in trading cycle for {symbol}: {e}", exc_info=True)
            # Return a graceful failure so scheduler continues
            return {"success": False, "error": str(e), "symbol": symbol}
    
    def _check_risk_management(self):
        """Check risk management rules for all positions across all symbols."""
        try:
            # Get current positions for all symbols
            positions = self.account_manager.get_positions()
            
            if not positions:
                logger.debug("No positions to check for risk")
                return
            
            logger.info(f"Checking risk for {len(positions)} position(s)")
            
            # Check stop-loss
            stop_loss_triggers = self.risk_manager.check_stop_loss(positions)
            for trigger in stop_loss_triggers:
                logger.warning(
                    f"Stop-loss triggered: {trigger['symbol']} "
                    f"({trigger['reason']})"
                )
                # Execute close position
                self._execute_risk_action(trigger)
            
            # Check take-profit (batch closing)
            take_profit_triggers = self.risk_manager.check_take_profit(positions)
            for trigger in take_profit_triggers:
                logger.info(
                    f"Take-profit triggered: {trigger['symbol']} "
                    f"({trigger['reason']})"
                )
                self._execute_risk_action(trigger)
            
            # Check max holding time
            holding_time_triggers = self.risk_manager.check_max_holding_time(positions)
            for trigger in holding_time_triggers:
                logger.warning(
                    f"Max holding time exceeded: {trigger['symbol']}"
                )
                self._execute_risk_action(trigger)
            
            # Check trailing stop
            trailing_triggers = self.risk_manager.check_trailing_stop(positions)
            for trigger in trailing_triggers:
                logger.info(
                    f"Trailing stop update: {trigger['symbol']} "
                    f"({trigger['message']})"
                )
            
        except Exception as e:
            logger.error(f"Error in risk management check: {e}", exc_info=True)
    
    def _execute_risk_action(self, action: dict):
        """Execute a risk management action."""
        try:
            from services.trade_execution import TradeExecutionService
            trade_exec = TradeExecutionService()
            
            symbol = action["symbol"]
            
            if action["action"] in ["close_position", "force_close"]:
                # Close position
                logger.info(f"Executing risk action: Close {symbol}")
                results = trade_exec.close_position(symbol, percentage=100)
                for result in results:
                    if result.get("status") == "FILLED":
                        logger.info(f"Successfully closed position: {symbol}")
                    else:
                        logger.error(
                            f"Failed to close position: {result.get('error')}"
                        )
            
            elif action["action"] == "partial_close":
                close_percent = action.get("close_percent", 30)
                logger.info(
                    f"Executing risk action: Partial close {symbol} "
                    f"({close_percent}%)"
                )
                results = trade_exec.close_position(symbol, percentage=close_percent)
                for result in results:
                    if result.get("status") == "FILLED":
                        logger.info(
                            f"Successfully closed {close_percent}% of {symbol}"
                        )
                    else:
                        logger.error(
                            f"Failed to partial close: {result.get('error')}"
                        )
        
        except Exception as e:
            logger.error(f"Error executing risk action: {e}", exc_info=True)
    
    def _job_executed(self, event):
        """Callback when a scheduled job executes successfully."""
        logger.debug(f"Job executed: {event.job_id}")
    
    def _job_error(self, event):
        """Callback when a scheduled job raises an error."""
        logger.error(f"Job error: {event.job_id} - {event.exception}")


def setup_signal_handlers(scheduler: TradingScheduler):
    """Setup signal handlers for graceful shutdown."""
    def signal_handler(sig, frame):
        logger.info(f"Received signal {sig}, shutting down...")
        scheduler.stop()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
