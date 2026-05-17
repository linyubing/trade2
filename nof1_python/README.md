# nof1.ai Clone - AI-Powered Crypto Trading Bot

A Python-based cryptocurrency quantitative trading platform that clones nof1.ai's functionality, using AI (LLM) for autonomous trading decisions.

## Features

- **AI-Driven Trading**: Uses LLM (OpenAI compatible API) for market analysis and trading decisions
- **Binance Testnet Integration**: Safe testing with virtual funds
- **Multi-Timeframe Analysis**: Analyzes 5m, 15m, 1h, 4h timeframes
- **16 Built-in Tools**: LLM can call tools for market data, technical indicators, order management
- **Risk Management**: Stop-loss, take-profit, position limits, max holding time
- **MySQL Database**: Stores account snapshots, positions, trades, AI decisions
- **APScheduler**: Periodic trading cycle execution

## Project Structure

```
nof1_python/
├── scheduler/
│   ├── __init__.py
│   └── trading_loop.py          # Main trading loop scheduler
├── agent/
│   ├── __init__.py
│   └── trading_agent.py         # AI Agent core logic
├── services/
│   ├── __init__.py
│   ├── market_data.py           # Market data fetching
│   ├── trade_execution.py       # Trade execution
│   └── account_manager.py       # Account management
├── risk/
│   ├── __init__.py
│   └── risk_manager.py         # Risk management
├── database/
│   ├── __init__.py
│   ├── database.py              # Database connection
│   └── models.py               # SQLAlchemy models
├── config/
│   ├── __init__.py
│   └── config.py               # Configuration management
├── utils/
│   ├── __init__.py
│   ├── logger.py                # Logging configuration
│   └── time_utils.py           # Time utilities
├── .env                         # Environment variables (create from .env.example)
├── requirements.txt             # Python dependencies
├── main.py                      # Program entry point
└── README.md                   # This file
```

## Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd nof1_python
   ```

2. **Create and configure .env file**
   ```bash
   cp .env.example .env
   ```
   
   Edit `.env` with your configuration:
   - `BINANCE_API_KEY` and `BINANCE_API_SECRET`: Get from [Binance Testnet](https://testnet.binance.vision/)
   - `OPENAI_API_KEY`: Your OpenAI API key (or compatible API)
   - `OPENAI_BASE_URL`: API base URL (default: https://api.openai.com/v1)
   - `AI_MODEL_NAME`: Model to use (e.g., gpt-4, deepseek-chat)
   - `DATABASE_URL`: MySQL connection string

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Setup MySQL database**
   ```sql
   CREATE DATABASE btc_quant CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
   ```

5. **Initialize database tables**
   The tables will be auto-created when you run the bot for the first time.

## Usage

### Start the trading bot

```bash
python main.py
```

The bot will:
1. Initialize database tables
2. Start the trading scheduler
3. Run trading cycles at the configured interval (default: 60 minutes)
4. AI will analyze market data and make trading decisions

### Configuration

Edit `.env` file to customize:

| Variable | Description | Default |
|----------|-------------|---------|
| `TRADING_SYMBOL` | Trading pair | BTCUSDT |
| `TRADING_INTERVAL_MINUTES` | Trading cycle interval | 60 |
| `STRATEGY` | Trading strategy | ai-autonomous |
| `MAX_POSITIONS` | Maximum open positions | 3 |
| `MAX_LEVERAGE` | Maximum leverage | 25 |
| `EXTREME_STOP_LOSS_PERCENT` | Hard stop-loss % | 5 |

## Trading Strategies

### ai-autonomous (Default)
Fully autonomous AI trader with self-reflection capability. The AI:
- Analyzes market data across multiple timeframes
- Performs self-reflection before each trading decision
- Learns from past trades
- Manages risk autonomously

### Other Strategies
- `conservative`: Low risk, max 5x leverage, max 2% risk per trade
- `balanced`: Moderate risk, max 10x leverage, max 3% risk per trade
- `aggressive`: High risk, max 20x leverage, max 5% risk per trade

## 16 AI Tools

The LLM can call these 16 tools:

1. `getMarketPrice(symbol)` - Get current price
2. `getTechnicalIndicators(symbol, timeframes)` - Get technical indicators
3. `getFundingRate(symbol)` - Get funding rate
4. `getOrderBook(symbol, limit)` - Get order book
5. `openPosition(symbol, side, leverage, amountUsdt)` - Open position
6. `closePosition(symbol, closePercent)` - Close position
7. `cancelOrder(symbol, orderId)` - Cancel order
8. `getAccountBalance()` - Get account balance
9. `getPositions()` - Get current positions
10. `getOpenOrders()` - Get open orders
11. `checkOrderStatus(orderId)` - Check order status
12. `calculateRisk(symbol, side, leverage, amountUsdt)` - Calculate risk
13. `syncPositions()` - Sync positions with exchange
14. `getCryptoNews(coin, limit)` - Get crypto news
15. `getExchangeAnnouncements(coin, limit)` - Get exchange announcements
16. `getLatestEvents(coin, limit)` - Get latest events

## Risk Management

### Automatic Protection (Code-Level)

- **Stop-Loss**:
  - Low leverage (≤5x): 8% stop-loss
  - Medium leverage (6-15x): 6% stop-loss
  - High leverage (>15x): 5% stop-loss

- **Take-Profit (Batch Closing)**:
  - 8% profit → Close 30%
  - 12% profit → Close 30%
  - 18% profit → Close 40%

- **Trailing Stop**:
  - 5% profit → Move stop to +2%
  - 10% profit → Move stop to +5%
  - 15% profit → Move stop to +8%

### Hard Limits

- **Extreme Stop-Loss**: 5% (forced close)
- **Max Holding Time**: 24 hours (forced close)
- **Max Positions**: 3 (configurable)
- **Max Leverage**: 25x (configurable)

## Database Schema

- `account_snapshots`: Account balance history
- `positions`: Current and historical positions
- `trades`: All executed trades
- `ai_decisions`: AI decision logs (for audit)
- `market_data`: Cached market data

## Logging

Logs are stored in `logs/` directory:
- Daily rotating log files
- Console output with colorized formatting
- Configurable log level via `LOG_LEVEL` in `.env`

## Safety Notes

⚠️ **Important**:
- This bot uses **Binance Testnet** by default (safe, virtual funds)
- To use real Binance (mainnet), set `BINANCE_TESTNET=False` in `.env`
- **Always test thoroughly on testnet before using real funds**
- AI decisions may not be profitable; this is for research/educational purposes
- Cryptocurrency trading carries significant risk; only trade with funds you can afford to lose

## Troubleshooting

### Database Connection Error
- Ensure MySQL is running
- Check `DATABASE_URL` in `.env`
- Verify database `btc_quant` exists

### Binance API Error
- Verify API keys are correct
- Ensure testnet keys are used with `BINANCE_TESTNET=True`
- Check API key permissions

### OpenAI API Error
- Verify `OPENAI_API_KEY` is set
- Check `OPENAI_BASE_URL` for compatible API
- Ensure you have sufficient API credits

## License

MIT License

## Disclaimer

This software is for educational and research purposes only. Do not use it for real trading without thorough testing. The authors are not responsible for any financial losses incurred using this software.
