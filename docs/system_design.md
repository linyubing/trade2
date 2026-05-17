# nof1.ai Clone - System Design & Task Decomposition

**Architect**: Bob (Software Architect)  
**Date**: 2025-05-16  
**Project**: Cryptocurrency Quantitative Trading Platform MVP

---

## Part A: System Design

### 1. Implementation Approach

#### 1.1 Core Technical Challenges

1. **Real-time Market Data Acquisition**: Continuous fetching of candlestick data from Binance Testnet
2. **LLM-based Decision Making**: Integrating OpenAI Function Calling with 16 trading tools
3. **Risk Management**: Pre-trade validation to prevent excessive losses
4. **Order Execution**: Reliable order placement and status tracking
5. **State Persistence**: Maintaining positions and account state in MySQL
6. **Scheduled Trading Cycles**: APScheduler-based periodic trading loop

#### 1.2 Framework and Library Selections

| Component | Selection | Justification |
|-----------|-----------|---------------|
| **Binance API** | `python-binance` 1.0.19+ | Official SDK, supports Testnet, async support |
| **LLM Integration** | `openai` 1.0+ | Latest SDK with Function Calling support |
| **Database ORM** | `SQLAlchemy` 2.0+ | Mature ORM, async support, good MySQL integration |
| **MySQL Driver** | `PyMySQL` 1.1+ | Pure Python MySQL driver, no C dependencies |
| **Data Validation** | `Pydantic` 2.0+ | Type validation, integrates with OpenAI tool schemas |
| **Task Scheduling** | `APScheduler` 3.10+ | Cron-like scheduling, supports async jobs |
| **Logging** | `loguru` 0.7+ | Simple structured logging with rotation |
| **Environment** | `python-dotenv` 1.0+ | `.env` file support |

#### 1.3 Architecture Pattern

**Layered Architecture with Event-Driven Scheduling**:

```
┌─────────────────────────────────────────────────────────────┐
│                    APScheduler (Cron Trigger)               │
└────────────────────────┬────────────────────────────────────┘
                         │ triggers every 5 minutes
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                  Trading Loop (scheduler/)                  │
│  - Fetch account state                                       │
│  - Call Trading Agent                                        │
│  - Execute approved actions                                  │
│  - Update state                                              │
└────────────────────────┬────────────────────────────────────┘
                         │
         ┌───────────────┼───────────────┐
         ▼               ▼               ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│ Trading Agent│ │ Risk Manager │ │ Trade Exec   │
│ (agent/)     │ │ (risk/)      │ │ (services/)  │
└──────────────┘ └──────────────┘ └──────────────┘
         │               │               │
         └───────────────┼───────────────┘
                         ▼
┌─────────────────────────────────────────────────────────────┐
│              Services Layer (services/)                      │
│  - Market Data (Binance API)                                 │
│  - Account Manager (DB + Binance)                           │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│              Database Layer (database/)                      │
│  - MySQL (btc_quant)                                        │
│  - SQLAlchemy ORM                                           │
└─────────────────────────────────────────────────────────────┘
```

---

### 2. File List

```
nof1_python/
├── scheduler/
│   ├── __init__.py
│   └── trading_loop.py          # Main trading loop logic
├── agent/
│   ├── __init__.py
│   └── trading_agent.py         # LLM agent with 16 function tools
├── services/
│   ├── __init__.py
│   ├── market_data.py           # Binance market data fetching
│   ├── trade_execution.py       # Order placement & tracking
│   └── account_manager.py       # Account & position management
├── risk/
│   ├── __init__.py
│   └── risk_manager.py          # Pre-trade risk validation
├── database/
│   ├── __init__.py
│   ├── database.py              # SQLAlchemy engine & session
│   └── models.py               # ORM models (7 tables)
├── config/
│   ├── __init__.py
│   └── config.py                # Configuration management
├── utils/
│   ├── __init__.py
│   ├── logger.py                # Loguru configuration
│   └── time_utils.py            # Time zone & formatting utils
├── .env.example                 # Environment variable template
├── requirements.txt              # Python dependencies
├── main.py                      # Entry point
└── README.md                    # Project documentation
```

**Total: 20 files** (including `__init__.py` files)

---

### 3. Data Structures and Interfaces

```mermaid
classDiagram
    %% Database Models
    class Account {
        +String account_id
        +String api_key_hash
        +Decimal balance_usdt
        +Decimal unrealized_pnl
        +Decimal total_equity
        +DateTime updated_at
        +to_dict() Dict
    }

    class Position {
        +String position_id
        +String account_id
        +String symbol
        +String side
        +Decimal quantity
        +Decimal entry_price
        +Decimal mark_price
        +Decimal unrealized_pnl
        +DateTime opened_at
        +to_dict() Dict
    }

    class Order {
        +String order_id
        +String account_id
        +String symbol
        +String side
        +String type
        +Decimal quantity
        +Decimal price
        +String status
        +DateTime created_at
        +to_dict() Dict
    }

    class Trade {
        +String trade_id
        +String order_id
        +String account_id
        +String symbol
        +String side
        +Decimal quantity
        +Decimal price
        +Decimal commission
        +DateTime executed_at
        +to_dict() Dict
    }

    class MarketData {
        +String id
        +String symbol
        +String interval
        +BigInteger open_time
        +Decimal open
        +Decimal high
        +Decimal low
        +Decimal close
        +Decimal volume
        +BigInteger close_time
        +DateTime created_at
        +to_dict() Dict
    }

    class AgentDecision {
        +String decision_id
        +String account_id
        +String symbol
        +String action
        +Dict reasoning
        +String risk_check_result
        +DateTime decided_at
        +to_dict() Dict
    }

    class RiskEvent {
        +String event_id
        +String account_id
        +String event_type
        +Dict details
        +DateTime triggered_at
        +to_dict() Dict
    }

    %% Service Classes
    class Config {
        <<Singleton>>
        +String BINANCE_API_KEY
        +String BINANCE_API_SECRET
        +String OPENAI_API_KEY
        +String DATABASE_URL
        +Decimal MAX_POSITION_SIZE
        +Decimal MAX_DAILY_LOSS
        +load_config() Config
    }

    class Database {
        <<Singleton>>
        +Engine engine
        +SessionLocal session
        +init_db() void
        +get_db() Session
    }

    class MarketDataService {
        -Client client
        +get_klines(symbol, interval, limit) List~Dict~
        +get_ticker(symbol) Dict
        +get_account_balance() Dict
    }

    class AccountManager {
        -Session db
        -Client client
        +sync_account_state(account_id) Account
        +get_positions(account_id) List~Position~
        +update_position(position) void
    }

    class TradeExecutionService {
        -Session db
        -Client client
        -RiskManager risk_manager
        +place_order(account_id, symbol, side, qty, price) Order
        +cancel_order(account_id, order_id) bool
        +get_open_orders(account_id) List~Order~
    }

    class RiskManager {
        -Config config
        -Session db
        +validate_order(account_id, symbol, side, qty, price) Tuple~bool, str~
        +check_daily_loss(account_id) Tuple~bool, str~
        +check_position_limit(account_id, symbol) Tuple~bool, str~
    }

    class TradingAgent {
        -Config config
        -MarketDataService market_data
        -AccountManager account_mgr
        -TradeExecutionService trade_exec
        -RiskManager risk_mgr
        +tools List~Dict~
        +run_trading_cycle(account_id, symbol) Dict
        -_setup_tools() List~Dict~
        -_call_llm(messages) Dict
    }

    class TradingLoop {
        -TradingAgent agent
        -List~str~ symbols
        +run() void
        -_process_symbol(account_id, symbol) void
    }

    %% Relationships
    Account "1" --> "*" Position
    Account "1" --> "*" Order
    Account "1" --> "*" Trade
    Order "1" --> "*" Trade
    Account "1" --> "*" AgentDecision
    Account "1" --> "*" RiskEvent

    TradingLoop --> TradingAgent
    TradingAgent --> MarketDataService
    TradingAgent --> AccountManager
    TradingAgent --> TradeExecutionService
    TradingAgent --> RiskManager
    TradeExecutionService --> RiskManager
    MarketDataService --> Config
    AccountManager --> Database
    TradeExecutionService --> Database
    RiskManager --> Config
```

---

### 4. Program Call Flow

```mermaid
sequenceDiagram
    participant S as Scheduler
    participant TL as TradingLoop
    participant AG as TradingAgent
    participant LLM as OpenAI API
    participant RM as RiskManager
    participant TE as TradeExecution
    participant MD as MarketDataService
    participant AM as AccountManager
    participant DB as Database

    Note over S,DB: System Initialization
    S->>TL: Start trading loop (every 5 min)
    TL->>AM: sync_account_state(account_id)
    AM->>DB: Query/Update account
    AM-->>TL: Return Account object

    Note over S,DB: Trading Cycle for Each Symbol
    TL->>AG: run_trading_cycle(account_id, symbol)
    
    AG->>MD: get_klines(symbol, "5m", 100)
    MD->>MD: Fetch from Binance Testnet
    MD-->>AG: Return OHLCV data
    
    AG->>MD: get_ticker(symbol)
    MD-->>AG: Return current price
    
    AG->>AM: get_positions(account_id)
    AM-->>AG: Return open positions
    
    Note over AG,LLM: LLM Decision Making
    AG->>LLM: chat.completions.create(messages, tools)
    LLM-->>AG: Return tool_calls or final decision
    
    alt LLM requests tool execution
        AG->>MD: execute tool (e.g., get_klines)
        MD-->>AG: Return tool result
        AG->>LLM: chat.completions.create(messages + tool_result)
        LLM-->>AG: Return final decision
    end

    AG-->>TL: Return decision (action, reasoning)

    alt Decision: OPEN position
        TL->>RM: validate_order(account_id, symbol, "BUY", qty, price)
        RM->>RM: Check daily loss limit
        RM->>RM: Check position limit
        RM-->>TL: Return (approved, reason)
        
        alt Risk Approved
            TL->>TE: place_order(account_id, symbol, "BUY", qty, price)
            TE->>TE: Submit to Binance Testnet
            TE->>DB: Save order to orders table
            TE-->>TL: Return Order object
            TL->>DB: Log AgentDecision
        else Risk Rejected
            TL->>DB: Log RiskEvent
        end
    end

    alt Decision: CLOSE position
        TL->>AM: get_positions(account_id, symbol)
        AM-->>TL: Return Position object
        TL->>TE: place_order(account_id, symbol, "SELL", qty, market_price)
        TE->>DB: Update order & create trade record
        TE-->>TL: Return Order object
        TL->>DB: Log AgentDecision
    end

    alt Decision: HOLD
        TL->>DB: Log AgentDecision (no action)
    end

    Note over S,DB: Cycle Complete
    TL-->>S: Cycle complete for symbol
    S->>S: Wait for next scheduled run
```

---

### 5. Anything UNCLEAR

1. **LLM Model Selection**: Which OpenAI model to use? (Recommend: `gpt-4-turbo-preview` for function calling reliability)

2. **Trading Pair List**: Which symbols to trade? (Assume: `BTCUSDT`, `ETHUSDT` initially)

3. **Scheduler Frequency**: How often to run trading loop? (Assume: every 5 minutes)

4. **Position Sizing**: How does LLM determine quantity? (Assume: fixed 10% of balance per trade, configurable)

5. **Backtesting Requirement**: Is historical backtesting needed for MVP? (Assume: No, live Testnet only)

6. **Web Dashboard**: Is a web UI needed? (Assume: No, CLI + logs only for MVP)

7. **Multiple Accounts**: Support multiple API keys? (Assume: Single account for MVP)

8. **Error Recovery**: How to handle Binance API failures? (Assume: log error, skip cycle, retry next time)

---

## Part B: Task Decomposition

### 6. Required Packages

```txt
# requirements.txt

# Core
python-dotenv==1.0.0
pydantic==2.5.0
pydantic-settings==2.1.0

# Binance API
python-binance==1.0.19

# OpenAI API
openai==1.3.0

# Database
sqlalchemy==2.0.23
pymysql==1.1.0

# Scheduling
apscheduler==3.10.4

# Logging
loguru==0.7.2

# Utilities
requests==2.31.0
pandas==2.1.4
numpy==1.26.2
```

---

### 7. Task List (Ordered by Dependency)

#### Task T01: Project Infrastructure & Configuration

**Task ID**: T01  
**Task Name**: Setup Project Infrastructure and Configuration Management  
**Source Files**:
- `config/config.py`
- `database/database.py`
- `utils/logger.py`
- `utils/time_utils.py`
- `.env.example`
- `requirements.txt`

**Dependencies**: None (Base task)  
**Priority**: P0

**Description**:
- Create configuration management with `pydantic-settings`
- Setup MySQL database connection with SQLAlchemy
- Configure loguru with rotation and structured output
- Create time utilities for consistent timestamps
- Provide `.env.example` template

---

#### Task T02: Database Models & Market Data Service

**Task ID**: T02  
**Task Name**: Implement Database Models and Market Data Service  
**Source Files**:
- `database/models.py`
- `services/market_data.py`
- `services/account_manager.py`

**Dependencies**: T01  
**Priority**: P0

**Description**:
- Define 7 database models (Account, Position, Order, Trade, MarketData, AgentDecision, RiskEvent)
- Implement `MarketDataService` to fetch klines, ticker, and account balance from Binance Testnet
- Implement `AccountManager` to sync account state and manage positions in DB

---

#### Task T03: Trading Agent with LLM Integration

**Task ID**: T03  
**Task Name**: Implement Trading Agent and Risk Manager  
**Source Files**:
- `agent/trading_agent.py`
- `risk/risk_manager.py`
- `services/trade_execution.py`

**Dependencies**: T01, T02  
**Priority**: P1

**Description**:
- Implement `TradingAgent` with OpenAI Function Calling (16 tools)
- Define System Prompt and User Message format (from PRD)
- Implement `RiskManager` with pre-trade validation (daily loss limit, position limit)
- Implement `TradeExecutionService` to place/cancel orders and track executions

---

#### Task T04: Trading Loop & Application Entry Point

**Task ID**: T04  
**Task Name**: Implement Trading Loop Scheduler and Main Entry Point  
**Source Files**:
- `scheduler/trading_loop.py`
- `main.py`
- `README.md`

**Dependencies**: T01, T02, T03  
**Priority**: P1

**Description**:
- Implement `TradingLoop` with APScheduler cron trigger (every 5 minutes)
- Orchestrate the trading cycle: fetch state → call agent → execute actions → update state
- Create `main.py` entry point with graceful shutdown handling
- Write `README.md` with setup and usage instructions

---

### 8. Shared Knowledge

```
# Cross-Cutting Concerns for Engineering Team

## 1. Environment Variables (.env)
- BINANCE_API_KEY: Binance Testnet API key
- BINANCE_API_SECRET: Binance Testnet API secret
- OPENAI_API_KEY: OpenAI API key
- DATABASE_URL: MySQL connection string (mysql+pymysql://user:pass@127.0.0.1:3306/btc_quant)

## 2. Database Conventions
- All tables use InnoDB engine with UTF8MB4 charset
- All timestamps stored as UTC (use time_utils for consistency)
- Use DECIMAL for all price/quantity fields (avoid float precision issues)
- Primary keys are UUID strings (use uuid.uuid4().hex)

## 3. Binance Testnet Configuration
- Base URL: https://testnet.binance.vision/api
- Use python-binance Client with testnet=True
- Get API keys from: https://testnet.binance.vision/

## 4. OpenAI Function Calling
- Model: gpt-4-turbo-preview (recommended)
- Tools: 16 functions defined in PRD (get_klines, place_order, etc.)
- System Prompt: As defined in PRD Section 3.2
- User Message Format: As defined in PRD Section 3.3

## 5. Risk Management Rules (Configurable)
- MAX_POSITION_SIZE: 0.1 (10% of balance per trade)
- MAX_DAILY_LOSS: 0.05 (5% max daily loss)
- MAX_OPEN_POSITIONS: 3
- MIN_TRADE_INTERVAL: 300 seconds (5 minutes)

## 6. Logging Standards
- Use loguru with rotation (10 MB per file, keep 5 files)
- Log levels: DEBUG (development), INFO (production)
- Log format: {time:YYYY-MM-DD HH:mm:ss} | {level} | {message}
- Log files location: ./logs/trading.log

## 7. Error Handling
- Binance API errors: log and skip current cycle (retry next scheduled run)
- OpenAI API errors: log, use fallback HOLD decision
- Database errors: log, attempt retry 3 times, then skip cycle
- All errors must be logged with stack trace

## 8. Graceful Shutdown
- Handle SIGINT/SIGTERM signals
- Complete current trading cycle before exiting
- Close all database sessions
- Cancel APScheduler jobs

## 9. Time Intervals
- Kline interval: "5m" (5-minute candles)
- Trading frequency: Every 5 minutes (cron: */5 * * * *)
- Market data limit: 100 candles (8 hours of 5m data)

## 10. Symbol Configuration
- Default trading pairs: ["BTCUSDT", "ETHUSDT"]
- Configurable via config.py
```

---

### 9. Task Dependency Graph

```mermaid
graph TD
    T01[Task T01: Project Infrastructure]
    T02[Task T02: Database Models & Market Data]
    T03[Task T03: Trading Agent & Risk Manager]
    T04[Task T04: Trading Loop & Entry Point]
    
    T01 --> T02
    T01 --> T03
    T02 --> T03
    T01 --> T04
    T02 --> T04
    T03 --> T04
    
    style T01 fill:#90EE90
    style T02 fill:#87CEEB
    style T03 fill:#FFD700
    style T04 fill:#FF6B6B
```

**Dependency Explanation**:
- **T01** (Infrastructure) must be completed first - provides config, DB connection, logging
- **T02** (Data Layer) depends on T01 - uses config and database
- **T03** (Core Logic) depends on T01 + T02 - uses market data and account manager
- **T04** (Integration) depends on all previous - ties everything together

---

## Appendix A: Trading Agent Function Tools (16 Tools)

As defined in PRD, the Trading Agent has access to 16 function calling tools:

1. `get_account_balance()` - Get USDT balance
2. `get_open_positions(symbol)` - Get open positions for symbol
3. `get_klines(symbol, interval, limit)` - Get OHLCV candlestick data
4. `get_ticker(symbol)` - Get current price ticker
5. `place_market_order(symbol, side, quantity)` - Place market order
6. `place_limit_order(symbol, side, quantity, price)` - Place limit order
7. `cancel_order(symbol, order_id)` - Cancel open order
8. `get_open_orders(symbol)` - Get pending orders
9. `get_order_status(symbol, order_id)` - Check order status
10. `calculate_position_size(symbol, risk_percent)` - Calculate order quantity
11. `get_historical_trades(symbol, limit)` - Get trade history
12. `set_stop_loss(symbol, stop_price)` - Set stop-loss order
13. `set_take_profit(symbol, take_price)` - Set take-profit order
14. `get_account_pnl(days)` - Get P&L over period
15. `log_decision(action, reasoning)` - Log trading decision
16. `check_risk_limits()` - Check if risk limits are breached

---

## Appendix B: Database Schema (SQL)

```sql
-- Database: btc_quant
-- Generated from models.py (SQLAlchemy)

CREATE DATABASE IF NOT EXISTS btc_quant 
    CHARACTER SET utf8mb4 
    COLLATE utf8mb4_unicode_ci;

USE btc_quant;

-- Accounts table
CREATE TABLE accounts (
    account_id VARCHAR(32) PRIMARY KEY,
    api_key_hash VARCHAR(64) NOT NULL,
    balance_usdt DECIMAL(18, 8) DEFAULT 0,
    unrealized_pnl DECIMAL(18, 8) DEFAULT 0,
    total_equity DECIMAL(18, 8) DEFAULT 0,
    updated_at DATETIME(6) NOT NULL,
    INDEX idx_updated_at (updated_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Positions table
CREATE TABLE positions (
    position_id VARCHAR(32) PRIMARY KEY,
    account_id VARCHAR(32) NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    side ENUM('LONG', 'SHORT') NOT NULL,
    quantity DECIMAL(18, 8) NOT NULL,
    entry_price DECIMAL(18, 8) NOT NULL,
    mark_price DECIMAL(18, 8),
    unrealized_pnl DECIMAL(18, 8) DEFAULT 0,
    opened_at DATETIME(6) NOT NULL,
    INDEX idx_account_symbol (account_id, symbol),
    FOREIGN KEY (account_id) REFERENCES accounts(account_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Orders table
CREATE TABLE orders (
    order_id VARCHAR(32) PRIMARY KEY,
    account_id VARCHAR(32) NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    side ENUM('BUY', 'SELL') NOT NULL,
    type ENUM('MARKET', 'LIMIT', 'STOP_LOSS', 'TAKE_PROFIT') NOT NULL,
    quantity DECIMAL(18, 8) NOT NULL,
    price DECIMAL(18, 8),
    status ENUM('NEW', 'PARTIALLY_FILLED', 'FILLED', 'CANCELED', 'REJECTED') NOT NULL,
    created_at DATETIME(6) NOT NULL,
    INDEX idx_account_status (account_id, status),
    INDEX idx_created_at (created_at),
    FOREIGN KEY (account_id) REFERENCES accounts(account_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Trades table
CREATE TABLE trades (
    trade_id VARCHAR(32) PRIMARY KEY,
    order_id VARCHAR(32) NOT NULL,
    account_id VARCHAR(32) NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    side ENUM('BUY', 'SELL') NOT NULL,
    quantity DECIMAL(18, 8) NOT NULL,
    price DECIMAL(18, 8) NOT NULL,
    commission DECIMAL(18, 8) DEFAULT 0,
    executed_at DATETIME(6) NOT NULL,
    INDEX idx_order_id (order_id),
    INDEX idx_executed_at (executed_at),
    FOREIGN KEY (order_id) REFERENCES orders(order_id),
    FOREIGN KEY (account_id) REFERENCES accounts(account_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Market data table
CREATE TABLE market_data (
    id VARCHAR(32) PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    interval VARCHAR(10) NOT NULL,
    open_time BIGINT NOT NULL,
    open DECIMAL(18, 8) NOT NULL,
    high DECIMAL(18, 8) NOT NULL,
    low DECIMAL(18, 8) NOT NULL,
    close DECIMAL(18, 8) NOT NULL,
    volume DECIMAL(18, 8) NOT NULL,
    close_time BIGINT NOT NULL,
    created_at DATETIME(6) NOT NULL,
    INDEX idx_symbol_interval_time (symbol, interval, open_time),
    UNIQUE KEY uk_symbol_interval_opentime (symbol, interval, open_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Agent decisions table
CREATE TABLE agent_decisions (
    decision_id VARCHAR(32) PRIMARY KEY,
    account_id VARCHAR(32) NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    action ENUM('OPEN', 'CLOSE', 'HOLD') NOT NULL,
    reasoning JSON NOT NULL,
    risk_check_result VARCHAR(500),
    decided_at DATETIME(6) NOT NULL,
    INDEX idx_account_decided (account_id, decided_at),
    FOREIGN KEY (account_id) REFERENCES accounts(account_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Risk events table
CREATE TABLE risk_events (
    event_id VARCHAR(32) PRIMARY KEY,
    account_id VARCHAR(32) NOT NULL,
    event_type VARCHAR(50) NOT NULL,
    details JSON NOT NULL,
    triggered_at DATETIME(6) NOT NULL,
    INDEX idx_account_triggered (account_id, triggered_at),
    FOREIGN KEY (account_id) REFERENCES accounts(account_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

---

**End of System Design Document**
