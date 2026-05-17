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
        
        logger.info(
            f"Starting trading scheduler "
            f"(interval={settings.TRADING_INTERVAL_MINUTES} minutes)"
        )
        
        # Add trading job
        trigger = IntervalTrigger(
            minutes=settings.TRADING_INTERVAL_MINUTES
        )
        self.scheduler.add_job(
            func=self._trading_cycle_wrapper,
            trigger=trigger,
            id='trading_cycle',
            name='Trading Cycle',
            replace_existing=True
        )
        
        # Start scheduler
        self.scheduler.start()
        self.is_running = True
        
        logger.info("Trading scheduler started successfully")
        
        # Run first cycle immediately
        logger.info("Running initial trading cycle...")
        self._trading_cycle_wrapper()
    
    def stop(self):
        """Stop the trading scheduler gracefully."""
        if not self.is_running:
            logger.warning("Scheduler is not running")
            return
        
        logger.info("Stopping trading scheduler...")
        self.scheduler.shutdown(wait=True)
        self.is_running = False
        logger.info("Trading scheduler stopped successfully")
    
    def _trading_cycle_wrapper(self):
        """Wrapper for trading cycle with error handling."""
        try:
            logger.info("=" * 60)
            logger.info("Starting new trading cycle")
            logger.info("=" * 60)
            
            # Check risk management (stop-loss, etc.)
            self._check_risk_management()
            
            # Run trading cycle
            result = self.trading_agent.run_trading_cycle()
            
            logger.info(f"Trading cycle completed: {result}")
            
        except Exception as e:
            logger.error(f"Error in trading cycle: {e}", exc_info=True)
    
    def _check_risk_management(self):
        """Check risk management rules (stop-loss, max holding time, etc.)."""
        try:
            # Get current positions
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
                result = trade_exec.close_position(symbol, 100)
                if result["success"]:
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
                result = trade_exec.close_position(symbol, close_percent)
                if result["success"]:
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
