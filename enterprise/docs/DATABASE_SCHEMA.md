# DragonScope Enterprise - Database Schema

## Overview

DragonScope Enterprise is a Bloomberg-grade financial terminal built on PostgreSQL 16+ with TimescaleDB 2.13+ extension. The schema is designed for:

- **High-frequency market data ingestion** (millions of ticks/sec)
- **Multi-tenant SaaS architecture** with row-level security
- **Real-time analytics** with continuous aggregates
- **Compliance-ready audit trails** with immutable logging
- **Horizontal scalability** via partitioning and distributed hypertables

---

## Extensions & Configuration

```sql
-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS timescaledb;
CREATE EXTENSION IF NOT EXISTS pg_crypto;        -- For UUID generation
CREATE EXTENSION IF NOT EXISTS btree_gist;       -- For exclusion constraints
CREATE EXTENSION IF NOT EXISTS pg_trgm;          -- For text search

-- TimescaleDB tuning parameters (postgresql.conf)
-- max_connections = 500
-- shared_buffers = 8GB
-- effective_cache_size = 24GB
-- maintenance_work_mem = 2GB
-- work_mem = 256MB
-- timescaledb.max_background_workers = 16
```

---

## Schema Organization

| Schema | Purpose | Data Retention |
|--------|---------|----------------|
| `market_data` | Time-series tick, quote, bar data | 1-7 years with tiered storage |
| `analytics` | Calculated risk metrics, portfolio analytics | 10 years |
| `trading` | Order lifecycle and execution data | 7 years (regulatory) |
| `research` | Research artifacts and user preferences | Indefinite |
| `enterprise` | Multi-tenancy, users, permissions | Indefinite |
| `audit` | Immutable audit logs | 10 years (compliance) |
| `ref_data` | Static reference data | Indefinite |

```sql
-- Create schemas
CREATE SCHEMA IF NOT EXISTS market_data;
CREATE SCHEMA IF NOT EXISTS analytics;
CREATE SCHEMA IF NOT EXISTS trading;
CREATE SCHEMA IF NOT EXISTS research;
CREATE SCHEMA IF NOT EXISTS enterprise;
CREATE SCHEMA IF NOT EXISTS audit;
CREATE SCHEMA IF NOT EXISTS ref_data;
```

---

## 1. Market Data Schema

### 1.1 Instruments (Reference Data)

```sql
-- Master instrument reference with SDC (Security Description Committee) standard fields
CREATE TABLE ref_data.instruments (
    instrument_id           BIGSERIAL PRIMARY KEY,
    symbol                  VARCHAR(32) NOT NULL,
    isin                    VARCHAR(12),
    cusip                   VARCHAR(9),
    sedol                   VARCHAR(7),
    bloomberg_ticker        VARCHAR(32),
    reuters_ric             VARCHAR(32),
    
    -- Instrument classification
    asset_class             VARCHAR(20) NOT NULL CHECK (asset_class IN (
        'EQUITY', 'ETF', 'FUTURE', 'OPTION', 'BOND', 'FX', 'CRYPTO', 'COMMODITY', 'INDEX'
    )),
    security_type           VARCHAR(30) NOT NULL,
    
    -- Exchange and market info
    exchange_code           VARCHAR(10) NOT NULL,
    mic_code                VARCHAR(4),  -- ISO 10383 Market Identifier Code
    currency                CHAR(3) NOT NULL,
    
    -- Corporate actions reference
    lot_size                INTEGER DEFAULT 1,
    tick_size               DECIMAL(18, 8),
    tick_value              DECIMAL(18, 8),
    
    -- Trading hours (in exchange local time)
    pre_market_start        TIME,
    pre_market_end          TIME,
    regular_start           TIME NOT NULL,
    regular_end             TIME NOT NULL,
    post_market_start       TIME,
    post_market_end         TIME,
    
    -- Status and metadata
    status                  VARCHAR(10) DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'INACTIVE', 'DELISTED', 'SUSPENDED')),
    listing_date            DATE,
    delisting_date          DATE,
    
    -- Corporate attributes
    issuer_name             VARCHAR(255),
    country_of_risk         CHAR(2),
    sector_gics             VARCHAR(8),
    industry_group          VARCHAR(50),
    
    -- Timestamps
    created_at              TIMESTAMPTZ DEFAULT NOW(),
    updated_at              TIMESTAMPTZ DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT uq_symbol_exchange UNIQUE (symbol, exchange_code),
    CONSTRAINT uq_isin UNIQUE (isin)
);

-- Index for symbol lookup
CREATE INDEX idx_instruments_symbol ON ref_data.instruments(symbol);
CREATE INDEX idx_instruments_isin ON ref_data.instruments(isin);
CREATE INDEX idx_instruments_bloomberg ON ref_data.instruments(bloomberg_ticker) WHERE bloomberg_ticker IS NOT NULL;
CREATE INDEX idx_instruments_asset_class ON ref_data.instruments(asset_class);
CREATE INDEX idx_instruments_status ON ref_data.instruments(status) WHERE status = 'ACTIVE';

-- Full-text search on issuer names
CREATE INDEX idx_instruments_issuer_trgm ON ref_data.instruments 
    USING gin (issuer_name gin_trgm_ops);
```

### 1.2 Tick Data (Trades)

```sql
-- Tick-by-tick trade data - partitioned by time and symbol
CREATE TABLE market_data.ticks (
    -- Time-series primary dimension
    ts                      TIMESTAMPTZ NOT NULL,
    
    -- Instrument reference
    instrument_id           BIGINT NOT NULL REFERENCES ref_data.instruments(instrument_id),
    
    -- Trade details
    trade_id                VARCHAR(64),  -- Exchange trade ID
    price                   DECIMAL(18, 8) NOT NULL,
    size                    BIGINT NOT NULL,
    
    -- Market context
    volume_weighted_price   DECIMAL(18, 8),
    
    -- Trade conditions and qualifiers
    trade_condition         VARCHAR(10),  -- Exchange-specific condition codes
    is_market_hours         BOOLEAN DEFAULT TRUE,
    is_auction              BOOLEAN DEFAULT FALSE,
    is_block_trade          BOOLEAN DEFAULT FALSE,
    is_dark_pool            BOOLEAN DEFAULT FALSE,
    
    -- Side indication (if available)
    aggressor_side          CHAR(1) CHECK (aggressor_side IN ('B', 'S', 'U')), -- Buy, Sell, Unknown
    
    -- Exchange and participant info
    exchange_code           VARCHAR(10),
    
    -- Metadata
    received_at             TIMESTAMPTZ DEFAULT NOW(),
    source                  VARCHAR(20) DEFAULT 'FEED',  -- FEED, BPIPE, RESTORED, etc.
    
    -- Tenant isolation (for multi-tenant deployments)
    tenant_id               BIGINT REFERENCES enterprise.tenants(tenant_id),
    
    PRIMARY KEY (ts, instrument_id, trade_id)
) PARTITION BY RANGE (ts);

-- Convert to hypertable with 1-day chunks for optimal query performance
SELECT create_hypertable(
    'market_data.ticks',
    'ts',
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists => TRUE,
    migrate_data => TRUE
);

-- Additional partitioning by instrument_id for parallel processing
-- Note: TimescaleDB 2.11+ supports space partitioning
SELECT add_dimension('market_data.ticks', 'instrument_id', number_partitions => 8);

-- Critical indexes for tick data
CREATE INDEX idx_ticks_instrument_ts ON market_data.ticks(instrument_id, ts DESC);
CREATE INDEX idx_ticks_condition ON market_data.ticks(trade_condition) WHERE trade_condition IS NOT NULL;
CREATE INDEX idx_ticks_block ON market_data.ticks(instrument_id, ts) WHERE is_block_trade = TRUE;

-- Compression policy: Compress chunks older than 7 days
ALTER TABLE market_data.ticks SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'instrument_id',
    timescaledb.compress_orderby = 'ts DESC'
);

SELECT add_compression_policy('market_data.ticks', INTERVAL '7 days');

-- Retention policy: Move to cold storage after 1 year, delete after 7 years
SELECT add_retention_policy('market_data.ticks', INTERVAL '7 years');
```

### 1.3 Quote Data (Level 1 & Level 2)

```sql
-- Quote updates - bid/ask changes including Level 2 book data
CREATE TABLE market_data.quotes (
    ts                      TIMESTAMPTZ NOT NULL,
    instrument_id           BIGINT NOT NULL REFERENCES ref_data.instruments(instrument_id),
    
    -- Quote identifier
    quote_seq_num           BIGINT,  -- Exchange sequence number for gap detection
    
    -- Level 1 (NBBO)
    bid_price               DECIMAL(18, 8),
    bid_size                BIGINT,
    ask_price               DECIMAL(18, 8),
    ask_size                BIGINT,
    
    -- Derived metrics
    spread                  DECIMAL(18, 8) GENERATED ALWAYS AS (
        CASE 
            WHEN bid_price IS NOT NULL AND ask_price IS NOT NULL 
            THEN ask_price - bid_price 
            ELSE NULL 
        END
    ) STORED,
    mid_price               DECIMAL(18, 8) GENERATED ALWAYS AS (
        CASE 
            WHEN bid_price IS NOT NULL AND ask_price IS NOT NULL 
            THEN (bid_price + ask_price) / 2 
            ELSE NULL 
        END
    ) STORED,
    
    -- Quote condition
    quote_condition         VARCHAR(10),
    is_nbbo                 BOOLEAN DEFAULT TRUE,  -- National Best Bid/Offer
    
    -- Exchange info
    exchange_code           VARCHAR(10),
    
    -- Metadata
    received_at             TIMESTAMPTZ DEFAULT NOW(),
    source                  VARCHAR(20) DEFAULT 'FEED',
    tenant_id               BIGINT REFERENCES enterprise.tenants(tenant_id),
    
    PRIMARY KEY (ts, instrument_id, quote_seq_num)
);

SELECT create_hypertable(
    'market_data.quotes',
    'ts',
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists => TRUE
);

SELECT add_dimension('market_data.quotes', 'instrument_id', number_partitions => 8);

CREATE INDEX idx_quotes_instrument_ts ON market_data.quotes(instrument_id, ts DESC);

-- Compression: Quotes compress very well due to similar values
ALTER TABLE market_data.quotes SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'instrument_id',
    timescaledb.compress_orderby = 'ts DESC'
);

SELECT add_compression_policy('market_data.quotes', INTERVAL '3 days');
SELECT add_retention_policy('market_data.quotes', INTERVAL '2 years');
```

### 1.4 Level 2 Order Book (Market Depth)

```sql
-- Market depth data (Level 2) - only for liquid instruments
CREATE TABLE market_data.order_book (
    ts                      TIMESTAMPTZ NOT NULL,
    instrument_id           BIGINT NOT NULL REFERENCES ref_data.instruments(instrument_id),
    
    -- Book level (0 = best bid/ask, 1 = next level, etc.)
    book_level              SMALLINT NOT NULL CHECK (book_level >= 0 AND book_level < 20),
    
    -- Side
    side                    CHAR(1) NOT NULL CHECK (side IN ('B', 'S')),  -- Bid or Ask
    
    -- Price level data
    price                   DECIMAL(18, 8) NOT NULL,
    size                    BIGINT NOT NULL,
    num_orders              INTEGER,  -- Number of orders at this level (if available)
    
    -- Exchange info
    exchange_code           VARCHAR(10),
    
    -- Metadata
    received_at             TIMESTAMPTZ DEFAULT NOW(),
    tenant_id               BIGINT REFERENCES enterprise.tenants(tenant_id),
    
    PRIMARY KEY (ts, instrument_id, book_level, side, price)
);

SELECT create_hypertable(
    'market_data.order_book',
    'ts',
    chunk_time_interval => INTERVAL '1 hour',  -- Smaller chunks due to high volume
    if_not_exists => TRUE
);

SELECT add_dimension('market_data.order_book', 'instrument_id', number_partitions => 16);

CREATE INDEX idx_orderbook_instrument_ts ON market_data.order_book(instrument_id, ts DESC, book_level);

-- Aggressive compression due to high volume
ALTER TABLE market_data.order_book SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'instrument_id, book_level, side',
    timescaledb.compress_orderby = 'ts DESC'
);

SELECT add_compression_policy('market_data.order_book', INTERVAL '1 day');
SELECT add_retention_policy('market_data.order_book', INTERVAL '90 days');  -- Shorter retention for L2
```

### 1.5 OHLCV Bars (Aggregated Data)

```sql
-- Candle/OHLCV data - multiple timeframes stored in one table
CREATE TABLE market_data.bars (
    ts                      TIMESTAMPTZ NOT NULL,
    instrument_id           BIGINT NOT NULL REFERENCES ref_data.instruments(instrument_id),
    
    -- Bar timeframe
    timeframe               VARCHAR(10) NOT NULL CHECK (timeframe IN (
        '1S', '5S', '15S', '30S',      -- Sub-minute
        '1M', '2M', '5M', '15M', '30M', -- Intraday
        '1H', '2H', '4H',               -- Hourly
        '1D', '1W', '1MO', '1Y'         -- Daily and above
    )),
    
    -- OHLCV
    open                    DECIMAL(18, 8) NOT NULL,
    high                    DECIMAL(18, 8) NOT NULL,
    low                     DECIMAL(18, 8) NOT NULL,
    close                   DECIMAL(18, 8) NOT NULL,
    volume                  BIGINT NOT NULL,
    
    -- Extended data
    vwap                    DECIMAL(18, 8),
    trades_count            INTEGER,  -- Number of trades in bar
    
    -- Auction data (for daily bars)
    open_auction_price      DECIMAL(18, 8),
    open_auction_volume     BIGINT,
    close_auction_price     DECIMAL(18, 8),
    close_auction_volume    BIGINT,
    
    -- Bid/Ask metrics
    bid_volume              BIGINT,
    ask_volume              BIGINT,
    
    -- Metadata
    is_complete             BOOLEAN DEFAULT TRUE,  -- Bar is complete (not partial)
    adjusted                BOOLEAN DEFAULT FALSE, -- Split/dividend adjusted
    source                  VARCHAR(20) DEFAULT 'AGGREGATED',
    tenant_id               BIGINT REFERENCES enterprise.tenants(tenant_id),
    
    PRIMARY KEY (ts, instrument_id, timeframe)
);

SELECT create_hypertable(
    'market_data.bars',
    'ts',
    chunk_time_interval => INTERVAL '1 month',
    if_not_exists => TRUE
);

SELECT add_dimension('market_data.bars', 'instrument_id', number_partitions => 4);

-- Indexes optimized for bar queries
CREATE INDEX idx_bars_instrument_timeframe ON market_data.bars(instrument_id, timeframe, ts DESC);
CREATE INDEX idx_bars_timeframe ON market_data.bars(timeframe, ts DESC);

-- Different compression for different timeframes
ALTER TABLE market_data.bars SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'instrument_id, timeframe',
    timescaledb.compress_orderby = 'ts DESC'
);

SELECT add_compression_policy('market_data.bars', INTERVAL '30 days');
SELECT add_retention_policy('market_data.bars', INTERVAL '10 years');
```

### 1.6 Continuous Aggregates

```sql
-- 1-minute bars from ticks (real-time aggregation)
CREATE MATERIALIZED VIEW market_data.bars_1m
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 minute', ts) AS ts,
    instrument_id,
    '1M'::VARCHAR(10) AS timeframe,
    first(price, ts) AS open,
    max(price) AS high,
    min(price) AS low,
    last(price, ts) AS close,
    sum(size) AS volume,
    sum(price * size) / NULLIF(sum(size), 0) AS vwap,
    count(*) AS trades_count,
    tenant_id
FROM market_data.ticks
GROUP BY time_bucket('1 minute', ts), instrument_id, tenant_id
WITH NO DATA;

-- Policy to refresh 1m bars
SELECT add_continuous_aggregate_policy('market_data.bars_1m',
    start_offset => INTERVAL '3 hours',
    end_offset => INTERVAL '1 minute',
    schedule_interval => INTERVAL '1 minute'
);

-- 5-minute bars from 1-minute
CREATE MATERIALIZED VIEW market_data.bars_5m
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('5 minutes', ts) AS ts,
    instrument_id,
    '5M'::VARCHAR(10) AS timeframe,
    first(open, ts) AS open,
    max(high) AS high,
    min(low) AS low,
    last(close, ts) AS close,
    sum(volume) AS volume,
    sum(vwap * volume) / NULLIF(sum(volume), 0) AS vwap,
    sum(trades_count) AS trades_count,
    tenant_id
FROM market_data.bars_1m
GROUP BY time_bucket('5 minutes', ts), instrument_id, tenant_id
WITH NO DATA;

-- Daily bars with all metrics
CREATE MATERIALIZED VIEW market_data.bars_1d
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 day', ts) AS ts,
    instrument_id,
    '1D'::VARCHAR(10) AS timeframe,
    first(open, ts) AS open,
    max(high) AS high,
    min(low) AS low,
    last(close, ts) AS close,
    sum(volume) AS volume,
    sum(vwap * volume) / NULLIF(sum(volume), 0) AS vwap,
    sum(trades_count) AS trades_count,
    tenant_id
FROM market_data.bars_1m
GROUP BY time_bucket('1 day', ts), instrument_id, tenant_id
WITH NO DATA;
```

---

## 2. Analytics Schema

### 2.1 Portfolios

```sql
-- Portfolio definitions
CREATE TABLE analytics.portfolios (
    portfolio_id            BIGSERIAL PRIMARY KEY,
    tenant_id               BIGINT NOT NULL REFERENCES enterprise.tenants(tenant_id),
    
    -- Identification
    portfolio_code          VARCHAR(50) NOT NULL,
    portfolio_name          VARCHAR(255) NOT NULL,
    portfolio_type          VARCHAR(20) NOT NULL CHECK (portfolio_type IN (
        'LONG_ONLY', 'LONG_SHORT', 'MARKET_NEUTRAL', 'INDEX_FUND', 
        'ETF', 'HEDGE_FUND', 'PENSION', 'ENDOWMENT'
    )),
    
    -- Benchmark and classification
    benchmark_symbol        VARCHAR(32),
    strategy                VARCHAR(50),
    investment_style        VARCHAR(20) CHECK (investment_style IN ('VALUE', 'GROWTH', 'BLEND')),
    
    -- Base currency
    base_currency           CHAR(3) NOT NULL DEFAULT 'USD',
    
    -- Inception and status
    inception_date          DATE NOT NULL,
    termination_date        DATE,
    status                  VARCHAR(10) DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'CLOSED', 'FROZEN')),
    
    -- Risk constraints
    target_volatility       DECIMAL(5, 4),
    max_drawdown_limit      DECIMAL(5, 4),
    leverage_limit          DECIMAL(5, 2) DEFAULT 1.00,
    
    -- Metadata
    aum                     DECIMAL(18, 2),  -- Assets under management
    created_by              BIGINT REFERENCES enterprise.users(user_id),
    created_at              TIMESTAMPTZ DEFAULT NOW(),
    updated_at              TIMESTAMPTZ DEFAULT NOW(),
    
    CONSTRAINT uq_portfolio_code_tenant UNIQUE (tenant_id, portfolio_code)
);

CREATE INDEX idx_portfolios_tenant ON analytics.portfolios(tenant_id);
CREATE INDEX idx_portfolios_status ON analytics.portfolios(status) WHERE status = 'ACTIVE';
```

### 2.2 Portfolio Holdings (Time-Weighted)

```sql
-- Portfolio holdings with temporal validity (SCD Type 2 pattern)
CREATE TABLE analytics.holdings (
    holding_id              BIGSERIAL,
    tenant_id               BIGINT NOT NULL REFERENCES enterprise.tenants(tenant_id),
    portfolio_id            BIGINT NOT NULL REFERENCES analytics.portfolios(portfolio_id),
    instrument_id           BIGINT NOT NULL REFERENCES ref_data.instruments(instrument_id),
    
    -- Position details
    quantity                DECIMAL(18, 8) NOT NULL,
    avg_cost_basis          DECIMAL(18, 8),
    total_cost_basis        DECIMAL(18, 2),
    
    -- Market values (snapshot at as_of_date)
    market_price            DECIMAL(18, 8),
    market_value            DECIMAL(18, 2),
    unrealized_pnl          DECIMAL(18, 2),
    
    -- Temporal validity
    valid_from              TIMESTAMPTZ NOT NULL,
    valid_to                TIMESTAMPTZ,  -- NULL means current
    
    -- Metadata
    as_of_date              DATE NOT NULL,
    created_at              TIMESTAMPTZ DEFAULT NOW(),
    
    PRIMARY KEY (holding_id, valid_from),
    CONSTRAINT uq_holdings_current EXCLUDE USING gist (
        tenant_id WITH =,
        portfolio_id WITH =,
        instrument_id WITH =,
        valid_from WITH &&
    ) WHERE (valid_to IS NULL)
);

SELECT create_hypertable(
    'analytics.holdings',
    'valid_from',
    chunk_time_interval => INTERVAL '1 month',
    if_not_exists => TRUE
);

CREATE INDEX idx_holdings_portfolio ON analytics.holdings(portfolio_id, valid_from DESC);
CREATE INDEX idx_holdings_instrument ON analytics.holdings(instrument_id);
CREATE INDEX idx_holdings_as_of ON analytics.holdings(as_of_date);
```

### 2.3 Risk Metrics

```sql
-- Daily risk calculations for portfolios and positions
CREATE TABLE analytics.risk_metrics (
    calculation_date        DATE NOT NULL,
    tenant_id               BIGINT NOT NULL REFERENCES enterprise.tenants(tenant_id),
    
    -- Entity being measured (portfolio or instrument)
    entity_type             VARCHAR(10) NOT NULL CHECK (entity_type IN ('PORTFOLIO', 'POSITION', 'INSTRUMENT')),
    entity_id               BIGINT NOT NULL,  -- portfolio_id or instrument_id
    
    -- VaR Metrics
    var_95_1d               DECIMAL(18, 4),  -- 95% confidence, 1 day
    var_99_1d               DECIMAL(18, 4),  -- 99% confidence, 1 day
    var_95_10d              DECIMAL(18, 4),  -- 95% confidence, 10 day (regulatory)
    var_99_10d              DECIMAL(18, 4),  -- 99% confidence, 10 day (regulatory)
    
    -- CVaR / Expected Shortfall
    cvar_95                 DECIMAL(18, 4),
    cvar_99                 DECIMAL(18, 4),
    
    -- VaR methodology
    var_methodology         VARCHAR(10) DEFAULT 'HISTORICAL' CHECK (var_methodology IN ('HISTORICAL', 'PARAMETRIC', 'MONTE_CARLO')),
    
    -- Volatility and Correlation
    realized_vol_30d        DECIMAL(10, 6),
    realized_vol_90d        DECIMAL(10, 6),
    realized_vol_252d       DECIMAL(10, 6),
    implied_vol             DECIMAL(10, 6),  -- For options
    
    -- Tail risk metrics
    skewness                DECIMAL(10, 6),
    kurtosis                DECIMAL(10, 6),
    max_drawdown_current    DECIMAL(10, 6),
    max_drawdown_1y         DECIMAL(10, 6),
    
    -- Liquidity metrics
    avg_daily_volume_30d    BIGINT,
    liquidity_score         DECIMAL(5, 2),  -- 0-100 scale
    
    -- Concentration
    herfindahl_index        DECIMAL(10, 6),  -- Concentration measure
    top_10_concentration    DECIMAL(5, 4),   -- % of portfolio
    
    -- Calculation metadata
    calculation_time        TIMESTAMPTZ DEFAULT NOW(),
    lookback_days           INTEGER DEFAULT 252,
    
    PRIMARY KEY (calculation_date, tenant_id, entity_type, entity_id)
);

SELECT create_hypertable(
    'analytics.risk_metrics',
    'calculation_date',
    chunk_time_interval => INTERVAL '1 year',
    if_not_exists => TRUE
);

CREATE INDEX idx_risk_metrics_tenant ON analytics.risk_metrics(tenant_id, calculation_date DESC);
CREATE INDEX idx_risk_metrics_entity ON analytics.risk_metrics(entity_type, entity_id, calculation_date DESC);
CREATE INDEX idx_risk_metrics_var ON analytics.risk_metrics(var_95_1d) WHERE var_95_1d IS NOT NULL;
```

### 2.4 Greeks (Options Risk)

```sql
-- Option Greeks calculations
CREATE TABLE analytics.option_greeks (
    calculation_date        DATE NOT NULL,
    ts                      TIMESTAMPTZ NOT NULL,  -- Intraday calculation time
    tenant_id               BIGINT NOT NULL REFERENCES enterprise.tenants(tenant_id),
    instrument_id           BIGINT NOT NULL REFERENCES ref_data.instruments(instrument_id),
    
    -- Underlying reference
    underlying_price        DECIMAL(18, 8) NOT NULL,
    
    -- Option specifics
    strike_price            DECIMAL(18, 8) NOT NULL,
    expiration_date         DATE NOT NULL,
    option_type             CHAR(1) NOT NULL CHECK (option_type IN ('C', 'P')),
    days_to_expiration      INTEGER NOT NULL,
    
    -- Greeks
    delta                   DECIMAL(10, 6) NOT NULL,
    gamma                   DECIMAL(12, 8) NOT NULL,
    theta                   DECIMAL(12, 8) NOT NULL,  -- Daily theta
    vega                    DECIMAL(12, 8) NOT NULL,
    rho                     DECIMAL(12, 8) NOT NULL,
    
    -- Additional metrics
    implied_vol             DECIMAL(10, 6) NOT NULL,
    intrinsic_value         DECIMAL(18, 8),
    time_value              DECIMAL(18, 8),
    
    -- Calculation params
    risk_free_rate          DECIMAL(8, 6) DEFAULT 0.05,
    dividend_yield          DECIMAL(8, 6) DEFAULT 0,
    pricing_model           VARCHAR(10) DEFAULT 'BSM' CHECK (pricing_model IN ('BSM', 'BINOMIAL', 'MC')),
    
    PRIMARY KEY (ts, instrument_id)
);

SELECT create_hypertable(
    'analytics.option_greeks',
    'ts',
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists => TRUE
);

CREATE INDEX idx_greeks_instrument ON analytics.option_greeks(instrument_id, ts DESC);
CREATE INDEX idx_greeks_expiration ON analytics.option_greeks(expiration_date, ts);

-- Compress older greeks (they don't change historically)
ALTER TABLE analytics.option_greeks SET (timescaledb.compress);
SELECT add_compression_policy('analytics.option_greeks', INTERVAL '7 days');
```

### 2.5 Factor Exposures

```sql
-- Multi-factor risk model exposures
CREATE TABLE analytics.factor_exposures (
    calculation_date        DATE NOT NULL,
    tenant_id               BIGINT NOT NULL REFERENCES enterprise.tenants(tenant_id),
    portfolio_id            BIGINT NOT NULL REFERENCES analytics.portfolios(portfolio_id),
    
    -- Factor model reference
    model_id                VARCHAR(20) NOT NULL DEFAULT 'AXWW21',  -- Axioma, Barra, etc.
    
    -- Factor exposures (z-scores)
    market_beta             DECIMAL(10, 6),
    size_factor             DECIMAL(10, 6),
    value_factor            DECIMAL(10, 6),
    momentum_factor         DECIMAL(10, 6),
    quality_factor          DECIMAL(10, 6),
    volatility_factor       DECIMAL(10, 6),
    growth_factor           DECIMAL(10, 6),
    liquidity_factor        DECIMAL(10, 6),
    
    -- Country/Region factors
    us_exposure             DECIMAL(5, 4),
    europe_exposure         DECIMAL(5, 4),
    asia_pacific_exposure   DECIMAL(5, 4),
    emerging_exposure       DECIMAL(5, 4),
    
    -- Sector factors (GICS Level 1)
    energy_factor           DECIMAL(10, 6),
    materials_factor        DECIMAL(10, 6),
    industrials_factor      DECIMAL(10, 6),
    consumer_disc_factor    DECIMAL(10, 6),
    consumer_staples_factor DECIMAL(10, 6),
    health_care_factor      DECIMAL(10, 6),
    financials_factor       DECIMAL(10, 6),
    info_tech_factor        DECIMAL(10, 6),
    communication_factor    DECIMAL(10, 6),
    utilities_factor        DECIMAL(10, 6),
    real_estate_factor      DECIMAL(10, 6),
    
    -- Attribution
    factor_contribution     DECIMAL(10, 6),  -- P&L attribution from factors
    specific_contribution   DECIMAL(10, 6),  -- Idiosyncratic contribution
    r_squared               DECIMAL(5, 4),   -- Model fit
    
    PRIMARY KEY (calculation_date, tenant_id, portfolio_id, model_id)
);

SELECT create_hypertable(
    'analytics.factor_exposures',
    'calculation_date',
    chunk_time_interval => INTERVAL '1 year',
    if_not_exists => TRUE
);

CREATE INDEX idx_factor_exposures_portfolio ON analytics.factor_exposures(portfolio_id, calculation_date DESC);
```

### 2.6 Correlation Matrix (Rolling)

```sql
-- Rolling correlation calculations between assets
CREATE TABLE analytics.correlations (
    calculation_date        DATE NOT NULL,
    tenant_id               BIGINT NOT NULL REFERENCES enterprise.tenants(tenant_id),
    
    -- Asset pair
    instrument_id_1         BIGINT NOT NULL REFERENCES ref_data.instruments(instrument_id),
    instrument_id_2         BIGINT NOT NULL REFERENCES ref_data.instruments(instrument_id),
    
    -- Correlation metrics
    correlation_30d         DECIMAL(5, 4),
    correlation_90d         DECIMAL(5, 4),
    correlation_252d        DECIMAL(5, 4),
    
    -- Rolling beta (id_2 as market proxy)
    beta_30d                DECIMAL(10, 6),
    beta_90d                DECIMAL(10, 6),
    beta_252d               DECIMAL(10, 6),
    
    -- Covariance
    covariance_30d          DECIMAL(18, 10),
    covariance_90d          DECIMAL(18, 10),
    covariance_252d         DECIMAL(18, 10),
    
    -- Metadata
    lookback_days           INTEGER,
    data_points             INTEGER,
    
    PRIMARY KEY (calculation_date, tenant_id, instrument_id_1, instrument_id_2),
    CONSTRAINT chk_instrument_order CHECK (instrument_id_1 < instrument_id_2)
);

SELECT create_hypertable(
    'analytics.correlations',
    'calculation_date',
    chunk_time_interval => INTERVAL '1 year',
    if_not_exists => TRUE
);

CREATE INDEX idx_correlations_inst1 ON analytics.correlations(instrument_id_1, calculation_date DESC);
CREATE INDEX idx_correlations_inst2 ON analytics.correlations(instrument_id_2, calculation_date DESC);
```

### 2.7 Performance Returns

```sql
-- Daily returns for portfolios and benchmarks
CREATE TABLE analytics.returns (
    date                    DATE NOT NULL,
    tenant_id               BIGINT NOT NULL REFERENCES enterprise.tenants(tenant_id),
    
    -- Entity
    entity_type             VARCHAR(10) NOT NULL CHECK (entity_type IN ('PORTFOLIO', 'BENCHMARK', 'INSTRUMENT')),
    entity_id               BIGINT NOT NULL,
    
    -- Return types
    total_return            DECIMAL(12, 8) NOT NULL,  -- Including dividends
    price_return            DECIMAL(12, 8),           -- Price only
    currency_return         DECIMAL(12, 8),           -- FX impact
    income_return           DECIMAL(12, 8),           -- Dividends/interest
    
    -- Cumulative
    mtd_return              DECIMAL(12, 8),
    qtd_return              DECIMAL(12, 8),
    ytd_return              DECIMAL(12, 8),
    
    -- Risk-adjusted
    excess_return           DECIMAL(12, 8),  -- vs benchmark
    active_return           DECIMAL(12, 8),
    
    -- Currency
    currency                CHAR(3) NOT NULL,
    
    PRIMARY KEY (date, tenant_id, entity_type, entity_id, currency)
);

SELECT create_hypertable(
    'analytics.returns',
    'date',
    chunk_time_interval => INTERVAL '2 years',
    if_not_exists => TRUE
);

CREATE INDEX idx_returns_entity ON analytics.returns(entity_type, entity_id, date DESC);
CREATE INDEX idx_returns_tenant ON analytics.returns(tenant_id, date DESC);
```

---

## 3. Trading Schema

### 3.1 Orders (OMS)

```sql
-- Order Management System - central order book
CREATE TABLE trading.orders (
    order_id                BIGSERIAL PRIMARY KEY,
    tenant_id               BIGINT NOT NULL REFERENCES enterprise.tenants(tenant_id),
    
    -- Order identifiers
    client_order_id         VARCHAR(64) NOT NULL,  -- Client's order ID
    parent_order_id         BIGINT REFERENCES trading.orders(order_id),  -- For child orders
    
    -- Portfolio/Account
    portfolio_id            BIGINT NOT NULL REFERENCES analytics.portfolios(portfolio_id),
    strategy_id             VARCHAR(50),  -- Trading strategy
    
    -- Instrument
    instrument_id           BIGINT NOT NULL REFERENCES ref_data.instruments(instrument_id),
    
    -- Order details
    side                    CHAR(1) NOT NULL CHECK (side IN ('B', 'S', 'SS', 'BC')),  -- Buy, Sell, Short Sell, Buy to Cover
    order_type              VARCHAR(20) NOT NULL CHECK (order_type IN (
        'MARKET', 'LIMIT', 'STOP', 'STOP_LIMIT', 'MARKET_ON_CLOSE', 
        'LIMIT_ON_CLOSE', 'TWAP', 'VWAP', 'PEGGED', 'ICEBERG'
    )),
    
    -- Quantities
    quantity                DECIMAL(18, 8) NOT NULL,
    filled_quantity         DECIMAL(18, 8) DEFAULT 0,
    remaining_quantity      DECIMAL(18, 8) GENERATED ALWAYS AS (quantity - filled_quantity) STORED,
    
    -- Price levels
    limit_price             DECIMAL(18, 8),
    stop_price              DECIMAL(18, 8),
    avg_fill_price          DECIMAL(18, 8),
    
    -- Order behavior
    time_in_force           VARCHAR(10) DEFAULT 'DAY' CHECK (time_in_force IN ('DAY', 'GTC', 'IOC', 'FOK', 'OPG', 'CLS')),
    
    -- Execution instructions
    execution_instructions  VARCHAR(100),  -- JSON array of instructions
    
    -- Order status (FIX 4.4 standard)
    status                  VARCHAR(20) DEFAULT 'PENDING_NEW' CHECK (status IN (
        'PENDING_NEW', 'NEW', 'PARTIALLY_FILLED', 'FILLED', 
        'PENDING_CANCEL', 'CANCELED', 'REJECTED', 'EXPIRED', 'SUSPENDED'
    )),
    
    -- Destination
    destination             VARCHAR(20),  -- Exchange or broker
    destination_type        VARCHAR(10) CHECK (destination_type IN ('EXCHANGE', 'DARK_POOL', 'INTERNAL', 'ALGO')),
    
    -- Timestamps
    created_at              TIMESTAMPTZ DEFAULT NOW(),
    transmitted_at          TIMESTAMPTZ,
    accepted_at             TIMESTAMPTZ,
    filled_at               TIMESTAMPTZ,
    canceled_at             TIMESTAMPTZ,
    expired_at              TIMESTAMPTZ,
    
    -- Audit
    created_by              BIGINT NOT NULL REFERENCES enterprise.users(user_id),
    updated_at              TIMESTAMPTZ DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT uq_client_order_id UNIQUE (tenant_id, client_order_id),
    CONSTRAINT chk_quantity_positive CHECK (quantity > 0),
    CONSTRAINT chk_limit_required CHECK (
        (order_type NOT IN ('LIMIT', 'STOP_LIMIT')) OR 
        (limit_price IS NOT NULL AND limit_price > 0)
    )
);

CREATE INDEX idx_orders_tenant ON trading.orders(tenant_id);
CREATE INDEX idx_orders_portfolio ON trading.orders(portfolio_id, created_at DESC);
CREATE INDEX idx_orders_instrument ON trading.orders(instrument_id, created_at DESC);
CREATE INDEX idx_orders_status ON trading.orders(status) WHERE status NOT IN ('FILLED', 'CANCELED', 'REJECTED', 'EXPIRED');
CREATE INDEX idx_orders_active ON trading.orders(tenant_id, portfolio_id, status) 
    WHERE status IN ('NEW', 'PARTIALLY_FILLED', 'PENDING_NEW');
CREATE INDEX idx_orders_client_id ON trading.orders(client_order_id);
```

### 3.2 Executions (Fills)

```sql
-- Execution reports / fills
CREATE TABLE trading.executions (
    execution_id            BIGSERIAL PRIMARY KEY,
    tenant_id               BIGINT NOT NULL REFERENCES enterprise.tenants(tenant_id),
    
    -- References
    order_id                BIGINT NOT NULL REFERENCES trading.orders(order_id),
    
    -- Execution identifiers
    execution_id_external   VARCHAR(64),  -- Exchange execution ID
    trade_id_external       VARCHAR(64),  -- Exchange trade ID (for reporting)
    
    -- Fill details
    fill_quantity           DECIMAL(18, 8) NOT NULL,
    fill_price              DECIMAL(18, 8) NOT NULL,
    
    -- Counterparty
    counterparty            VARCHAR(50),  -- Exchange, broker, contra firm
    liquidity_indicator     CHAR(1) CHECK (liquidity_indicator IN ('A', 'R', 'N')),  -- Added, Removed, Neither
    
    -- Fees and charges
    commission              DECIMAL(18, 4) DEFAULT 0,
    fees                    DECIMAL(18, 4) DEFAULT 0,
    taxes                   DECIMAL(18, 4) DEFAULT 0,
    
    -- Notional
    gross_notional          DECIMAL(18, 4) GENERATED ALWAYS AS (fill_quantity * fill_price) STORED,
    net_notional            DECIMAL(18, 4) GENERATED ALWAYS AS (
        fill_quantity * fill_price + COALESCE(commission, 0) + COALESCE(fees, 0) + COALESCE(taxes, 0)
    ) STORED,
    
    -- Market context at time of fill
    bid_price               DECIMAL(18, 8),
    ask_price               DECIMAL(18, 8),
    mid_price               DECIMAL(18, 8),
    
    -- FIX-related
    fix_exec_type           CHAR(1),
    fix_exec_trans_type     CHAR(1),
    
    -- Timestamps
    execution_ts            TIMESTAMPTZ NOT NULL,
    received_at             TIMESTAMPTZ DEFAULT NOW(),
    booked_at               TIMESTAMPTZ,
    
    -- Audit
    created_at              TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_executions_order ON trading.executions(order_id);
CREATE INDEX idx_executions_tenant_ts ON trading.executions(tenant_id, execution_ts DESC);
CREATE INDEX idx_executions_instrument ON trading.executions(execution_ts DESC) 
    INCLUDE (order_id, fill_quantity, fill_price);

-- Trigger to update order status on execution
CREATE OR REPLACE FUNCTION trading.update_order_on_execution()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE trading.orders
    SET 
        filled_quantity = filled_quantity + NEW.fill_quantity,
        avg_fill_price = (
            SELECT SUM(fill_quantity * fill_price) / NULLIF(SUM(fill_quantity), 0)
            FROM trading.executions
            WHERE order_id = NEW.order_id
        ),
        status = CASE 
            WHEN filled_quantity + NEW.fill_quantity >= quantity THEN 'FILLED'
            ELSE 'PARTIALLY_FILLED'
        END,
        filled_at = CASE 
            WHEN filled_quantity + NEW.fill_quantity >= quantity THEN NEW.execution_ts
            ELSE filled_at
        END,
        updated_at = NOW()
    WHERE order_id = NEW.order_id;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_update_order_on_execution
AFTER INSERT ON trading.executions
FOR EACH ROW
EXECUTE FUNCTION trading.update_order_on_execution();
```

### 3.3 Allocations (Post-Trade)

```sql
-- Trade allocations to sub-accounts or strategies
CREATE TABLE trading.allocations (
    allocation_id           BIGSERIAL PRIMARY KEY,
    tenant_id               BIGINT NOT NULL REFERENCES enterprise.tenants(tenant_id),
    execution_id            BIGINT NOT NULL REFERENCES trading.executions(execution_id),
    
    -- Allocation target
    sub_account_id          VARCHAR(50) NOT NULL,  -- Sub-account or strategy
    portfolio_id            BIGINT REFERENCES analytics.portfolios(portfolio_id),
    
    -- Allocated quantity and price
    allocated_quantity      DECIMAL(18, 8) NOT NULL,
    allocated_price         DECIMAL(18, 8) NOT NULL,
    
    -- Pro-rata allocation method
    allocation_method       VARCHAR(20) DEFAULT 'PRO_RATA' CHECK (allocation_method IN (
        'PRO_RATA', 'LOT_ALLOCATION', 'PERCENTAGE', 'MANUAL', 'FIFO'
    )),
    allocation_percentage   DECIMAL(5, 4),
    
    -- Allocated charges
    allocated_commission    DECIMAL(18, 4) DEFAULT 0,
    allocated_fees          DECIMAL(18, 4) DEFAULT 0,
    allocated_taxes         DECIMAL(18, 4) DEFAULT 0,
    
    -- Status
    status                  VARCHAR(20) DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'CONFIRMED', 'REJECTED')),
    
    -- Reference data
    allocation_reference    VARCHAR(64),  -- External allocation ID
    
    -- Timestamps
    created_at              TIMESTAMPTZ DEFAULT NOW(),
    confirmed_at            TIMESTAMPTZ,
    
    -- Audit
    created_by              BIGINT REFERENCES enterprise.users(user_id),
    
    CONSTRAINT chk_allocation_quantity CHECK (allocated_quantity > 0)
);

CREATE INDEX idx_allocations_execution ON trading.allocations(execution_id);
CREATE INDEX idx_allocations_sub_account ON trading.allocations(sub_account_id);
CREATE INDEX idx_allocations_portfolio ON trading.allocations(portfolio_id);
```

### 3.4 Transaction Blotter

```sql
-- Unified transaction history (immutable)
CREATE TABLE trading.blotter (
    transaction_id          BIGSERIAL,
    tenant_id               BIGINT NOT NULL REFERENCES enterprise.tenants(tenant_id),
    
    -- Transaction identifiers
    transaction_type        VARCHAR(20) NOT NULL CHECK (transaction_type IN (
        'TRADE', 'CORPORATE_ACTION', 'TRANSFER_IN', 'TRANSFER_OUT', 
        'CASH_DIVIDEND', 'STOCK_DIVIDEND', 'SPLIT', 'MERGER', 'SPINOFF'
    )),
    
    -- References
    order_id                BIGINT REFERENCES trading.orders(order_id),
    execution_id            BIGINT REFERENCES trading.executions(execution_id),
    allocation_id           BIGINT REFERENCES trading.allocations(allocation_id),
    
    -- Portfolio and instrument
    portfolio_id            BIGINT NOT NULL REFERENCES analytics.portfolios(portfolio_id),
    instrument_id           BIGINT REFERENCES ref_data.instruments(instrument_id),
    
    -- Transaction details
    side                    VARCHAR(10) CHECK (side IN ('BUY', 'SELL', 'SHORT', 'COVER', 'CREDIT', 'DEBIT')),
    quantity                DECIMAL(18, 8),
    price                   DECIMAL(18, 8),
    currency                CHAR(3),
    fx_rate                 DECIMAL(18, 8) DEFAULT 1,
    
    -- Monetary amounts
    gross_amount            DECIMAL(18, 4),
    fees                    DECIMAL(18, 4) DEFAULT 0,
    taxes                   DECIMAL(18, 4) DEFAULT 0,
    net_amount              DECIMAL(18, 4),
    
    -- Corporate action details
    corporate_action_id     BIGINT,
    ca_type                 VARCHAR(20),
    ca_description          TEXT,
    
    -- Settlement
    trade_date              DATE NOT NULL,
    settlement_date         DATE,
    settlement_status       VARCHAR(10) DEFAULT 'PENDING' CHECK (settlement_status IN ('PENDING', 'SETTLED', 'FAILED')),
    
    -- Immutable timestamp
    transaction_ts          TIMESTAMPTZ NOT NULL,
    created_at              TIMESTAMPTZ DEFAULT NOW(),
    
    -- Audit - who booked this
    booked_by               BIGINT NOT NULL REFERENCES enterprise.users(user_id),
    booking_source          VARCHAR(20) DEFAULT 'MANUAL' CHECK (booking_source IN ('MANUAL', 'OMS', 'FILE_UPLOAD', 'API', 'CA')),
    
    PRIMARY KEY (transaction_id, transaction_ts)
);

SELECT create_hypertable(
    'trading.blotter',
    'transaction_ts',
    chunk_time_interval => INTERVAL '6 months',
    if_not_exists => TRUE
);

CREATE INDEX idx_blotter_tenant ON trading.blotter(tenant_id, transaction_ts DESC);
CREATE INDEX idx_blotter_portfolio ON trading.blotter(portfolio_id, transaction_ts DESC);
CREATE INDEX idx_blotter_instrument ON trading.blotter(instrument_id, transaction_ts DESC);
CREATE INDEX idx_blotter_trade_date ON trading.blotter(trade_date);
CREATE INDEX idx_blotter_settlement ON trading.blotter(settlement_status) WHERE settlement_status = 'PENDING';

-- Compression policy
ALTER TABLE trading.blotter SET (timescaledb.compress);
SELECT add_compression_policy('trading.blotter', INTERVAL '30 days');
SELECT add_retention_policy('trading.blotter', INTERVAL '10 years');
```

---

## 4. Research Schema

### 4.1 Research Notes

```sql
-- Research notes with versioning
CREATE TABLE research.notes (
    note_id                 BIGSERIAL PRIMARY KEY,
    tenant_id               BIGINT NOT NULL REFERENCES enterprise.tenants(tenant_id),
    
    -- Note metadata
    title                   VARCHAR(255) NOT NULL,
    content                 TEXT NOT NULL,
    content_format          VARCHAR(10) DEFAULT 'MARKDOWN' CHECK (content_format IN ('MARKDOWN', 'HTML', 'PLAIN')),
    
    -- Classification
    note_type               VARCHAR(20) NOT NULL CHECK (note_type IN (
        'EQUITY_RESEARCH', 'MARKET_COMMENTARY', 'STRATEGY', 'RISK_REPORT',
        'PORTFOLIO_REVIEW', 'TRADE_IDEA', 'MEETING_NOTES', 'NEWS_ANALYSIS'
    )),
    
    -- Related entities
    instrument_id           BIGINT REFERENCES ref_data.instruments(instrument_id),
    portfolio_id            BIGINT REFERENCES analytics.portfolios(portfolio_id),
    sector                  VARCHAR(50),
    tags                    TEXT[],  -- PostgreSQL array for tags
    
    -- Ratings/Outlook
    rating                  VARCHAR(10) CHECK (rating IN ('BUY', 'HOLD', 'SELL', 'STRONG_BUY', 'STRONG_SELL')),
    target_price            DECIMAL(18, 8),
    price_at_rating         DECIMAL(18, 8),
    
    -- Visibility
    visibility              VARCHAR(10) DEFAULT 'PRIVATE' CHECK (visibility IN ('PRIVATE', 'TEAM', 'DEPARTMENT', 'FIRM')),
    
    -- Versioning
    version                 INTEGER DEFAULT 1,
    parent_note_id          BIGINT REFERENCES research.notes(note_id),
    is_latest               BOOLEAN DEFAULT TRUE,
    
    -- Status workflow
    status                  VARCHAR(15) DEFAULT 'DRAFT' CHECK (status IN ('DRAFT', 'REVIEW', 'APPROVED', 'PUBLISHED', 'ARCHIVED')),
    
    -- Timestamps
    created_at              TIMESTAMPTZ DEFAULT NOW(),
    updated_at              TIMESTAMPTZ DEFAULT NOW(),
    published_at            TIMESTAMPTZ,
    
    -- Authors
    author_id               BIGINT NOT NULL REFERENCES enterprise.users(user_id),
    reviewer_id             BIGINT REFERENCES enterprise.users(user_id),
    approver_id             BIGINT REFERENCES enterprise.users(user_id),
    
    -- Search vector for full-text search
    search_vector           tsvector
);

-- Full-text search index
CREATE INDEX idx_notes_search ON research.notes USING gin(search_vector);
CREATE INDEX idx_notes_tenant ON research.notes(tenant_id, created_at DESC);
CREATE INDEX idx_notes_author ON research.notes(author_id);
CREATE INDEX idx_notes_instrument ON research.notes(instrument_id) WHERE instrument_id IS NOT NULL;
CREATE INDEX idx_notes_type ON research.notes(note_type, created_at DESC);
CREATE INDEX idx_notes_tags ON research.notes USING gin(tags);

-- Trigger to update search vector
CREATE OR REPLACE FUNCTION research.update_note_search_vector()
RETURNS TRIGGER AS $$
BEGIN
    NEW.search_vector := 
        setweight(to_tsvector('english', COALESCE(NEW.title, '')), 'A') ||
        setweight(to_tsvector('english', COALESCE(NEW.content, '')), 'B') ||
        setweight(to_tsvector('english', COALESCE(array_to_string(NEW.tags, ' '), '')), 'C');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_update_note_search_vector
BEFORE INSERT OR UPDATE ON research.notes
FOR EACH ROW
EXECUTE FUNCTION research.update_note_search_vector();
```

### 4.2 Watchlists

```sql
-- User and shared watchlists
CREATE TABLE research.watchlists (
    watchlist_id            BIGSERIAL PRIMARY KEY,
    tenant_id               BIGINT NOT NULL REFERENCES enterprise.tenants(tenant_id),
    
    -- Watchlist info
    name                    VARCHAR(100) NOT NULL,
    description             TEXT,
    
    -- Ownership
    owner_id                BIGINT NOT NULL REFERENCES enterprise.users(user_id),
    is_personal             BOOLEAN DEFAULT TRUE,
    
    -- Sharing
    is_shared               BOOLEAN DEFAULT FALSE,
    shared_with_team_id     BIGINT REFERENCES enterprise.teams(team_id),
    
    -- Metadata
    color                   VARCHAR(7),  -- Hex color code
    sort_order              INTEGER DEFAULT 0,
    
    -- Timestamps
    created_at              TIMESTAMPTZ DEFAULT NOW(),
    updated_at              TIMESTAMPTZ DEFAULT NOW(),
    
    CONSTRAINT uq_watchlist_name_owner UNIQUE (owner_id, name)
);

CREATE INDEX idx_watchlists_tenant ON research.watchlists(tenant_id);
CREATE INDEX idx_watchlists_owner ON research.watchlists(owner_id);
CREATE INDEX idx_watchlists_shared ON research.watchlists(is_shared) WHERE is_shared = TRUE;

-- Watchlist items
CREATE TABLE research.watchlist_items (
    item_id                 BIGSERIAL PRIMARY KEY,
    watchlist_id            BIGINT NOT NULL REFERENCES research.watchlists(watchlist_id) ON DELETE CASCADE,
    instrument_id           BIGINT NOT NULL REFERENCES ref_data.instruments(instrument_id),
    
    -- Item details
    display_order           INTEGER DEFAULT 0,
    notes                   TEXT,
    alert_enabled           BOOLEAN DEFAULT FALSE,
    
    -- User annotations
    user_notes              TEXT,
    tags                    TEXT[],
    
    -- Timestamps
    added_at                TIMESTAMPTZ DEFAULT NOW(),
    
    CONSTRAINT uq_watchlist_item UNIQUE (watchlist_id, instrument_id)
);

CREATE INDEX idx_watchlist_items_watchlist ON research.watchlist_items(watchlist_id);
CREATE INDEX idx_watchlist_items_instrument ON research.watchlist_items(instrument_id);
```

### 4.3 Screeners

```sql
-- Saved stock/ETF screeners
CREATE TABLE research.screeners (
    screener_id             BIGSERIAL PRIMARY KEY,
    tenant_id               BIGINT NOT NULL REFERENCES enterprise.tenants(tenant_id),
    
    -- Basic info
    name                    VARCHAR(100) NOT NULL,
    description             TEXT,
    
    -- Universe
    asset_class             VARCHAR(20),  -- Filter by asset class
    exchanges               TEXT[],       -- Filter by exchanges
    sectors                 TEXT[],       -- Filter by GICS sectors
    countries               TEXT[],       -- Filter by country of risk
    
    -- Criteria (stored as JSON for flexibility)
    criteria                JSONB NOT NULL DEFAULT '{}',
    -- Example criteria structure:
    -- {
    --   "market_cap": { "min": 1000000000, "max": null },
    --   "pe_ratio": { "min": 5, "max": 30 },
    --   "dividend_yield": { "min": 0.02, "max": null },
    --   "rsi_14": { "min": null, "max": 30 },
    --   "avg_volume_30d": { "min": 1000000, "max": null }
    -- }
    
    -- Sorting
    sort_by                 VARCHAR(50) DEFAULT 'market_cap',
    sort_order              VARCHAR(4) DEFAULT 'DESC' CHECK (sort_order IN ('ASC', 'DESC')),
    
    -- Results limit
    max_results             INTEGER DEFAULT 100,
    
    -- Ownership
    owner_id                BIGINT NOT NULL REFERENCES enterprise.users(user_id),
    is_shared               BOOLEAN DEFAULT FALSE,
    
    -- Execution
    last_run_at             TIMESTAMPTZ,
    last_result_count       INTEGER,
    
    -- Scheduling
    is_scheduled            BOOLEAN DEFAULT FALSE,
    schedule_cron           VARCHAR(100),  -- Cron expression for scheduled runs
    
    -- Timestamps
    created_at              TIMESTAMPTZ DEFAULT NOW(),
    updated_at              TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_screeners_tenant ON research.screeners(tenant_id);
CREATE INDEX idx_screeners_owner ON research.screeners(owner_id);
CREATE INDEX idx_screeners_criteria ON research.screeners USING gin(criteria);
```

### 4.4 Alerts

```sql
-- Alert conditions and trigger history
CREATE TABLE research.alerts (
    alert_id                BIGSERIAL PRIMARY KEY,
    tenant_id               BIGINT NOT NULL REFERENCES enterprise.tenants(tenant_id),
    
    -- Alert definition
    name                    VARCHAR(100) NOT NULL,
    description             TEXT,
    
    -- Alert type
    alert_type              VARCHAR(20) NOT NULL CHECK (alert_type IN (
        'PRICE_THRESHOLD', 'PRICE_CHANGE_PCT', 'VOLUME_SPIKE',
        'TECHNICAL_INDICATOR', 'FUNDAMENTAL', 'NEWS_KEYWORD',
        'PORTFOLIO_RISK', 'CORPORATE_ACTION', 'CUSTOM'
    )),
    
    -- Target (instrument, portfolio, or watchlist)
    target_type             VARCHAR(15) NOT NULL CHECK (target_type IN ('INSTRUMENT', 'PORTFOLIO', 'WATCHLIST', 'CUSTOM')),
    target_id               BIGINT,  -- ID of instrument/portfolio/watchlist
    
    -- Condition (JSON structure)
    condition               JSONB NOT NULL,
    -- Example conditions:
    -- Price threshold: {"field": "price", "operator": ">=", "value": 150.00}
    -- Price change: {"field": "change_pct", "operator": ">", "value": 5}
    -- Volume spike: {"field": "volume_ratio", "operator": ">", "value": 3}
    -- RSI: {"field": "rsi_14", "operator": "<", "value": 30}
    
    -- Trigger behavior
    trigger_mode            VARCHAR(10) DEFAULT 'ONCE' CHECK (trigger_mode IN ('ONCE', 'REPEATING', 'COOLDOWN')),
    cooldown_minutes        INTEGER DEFAULT 60,  -- For COOLDOWN mode
    
    -- Notification channels
    notify_in_app           BOOLEAN DEFAULT TRUE,
    notify_email            BOOLEAN DEFAULT FALSE,
    notify_sms              BOOLEAN DEFAULT FALSE,
    notify_webhook          BOOLEAN DEFAULT FALSE,
    webhook_url             TEXT,
    
    -- Status
    status                  VARCHAR(10) DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'PAUSED', 'DISABLED')),
    
    -- Ownership
    owner_id                BIGINT NOT NULL REFERENCES enterprise.users(user_id),
    
    -- Statistics
    trigger_count           INTEGER DEFAULT 0,
    last_triggered_at       TIMESTAMPTZ,
    
    -- Timestamps
    created_at              TIMESTAMPTZ DEFAULT NOW(),
    updated_at              TIMESTAMPTZ DEFAULT NOW(),
    expires_at              TIMESTAMPTZ
);

CREATE INDEX idx_alerts_tenant ON research.alerts(tenant_id);
CREATE INDEX idx_alerts_owner ON research.alerts(owner_id);
CREATE INDEX idx_alerts_active ON research.alerts(status) WHERE status = 'ACTIVE';
CREATE INDEX idx_alerts_target ON research.alerts(target_type, target_id);
CREATE INDEX idx_alerts_type ON research.alerts(alert_type);

-- Alert trigger history
CREATE TABLE research.alert_history (
    trigger_id              BIGSERIAL,
    alert_id                BIGINT NOT NULL REFERENCES research.alerts(alert_id),
    tenant_id               BIGINT NOT NULL REFERENCES enterprise.tenants(tenant_id),
    
    -- Trigger details
    triggered_at            TIMESTAMPTZ NOT NULL,
    trigger_value           DECIMAL(18, 8),  -- The value that triggered
    trigger_data            JSONB,           -- Context at trigger time
    
    -- Status
    acknowledged            BOOLEAN DEFAULT FALSE,
    acknowledged_by         BIGINT REFERENCES enterprise.users(user_id),
    acknowledged_at         TIMESTAMPTZ,
    
    -- Notification status
    notification_sent       BOOLEAN DEFAULT FALSE,
    notification_error      TEXT,
    
    PRIMARY KEY (trigger_id, triggered_at)
);

SELECT create_hypertable(
    'research.alert_history',
    'triggered_at',
    chunk_time_interval => INTERVAL '1 month',
    if_not_exists => TRUE
);

CREATE INDEX idx_alert_history_alert ON research.alert_history(alert_id, triggered_at DESC);
CREATE INDEX idx_alert_history_tenant ON research.alert_history(tenant_id, triggered_at DESC);
```

---

## 5. Enterprise Schema

### 5.1 Tenants (Multi-tenancy)

```sql
-- Tenant/organization management
CREATE TABLE enterprise.tenants (
    tenant_id               BIGSERIAL PRIMARY KEY,
    
    -- Identification
    tenant_code             VARCHAR(50) NOT NULL UNIQUE,
    tenant_name             VARCHAR(255) NOT NULL,
    legal_name              VARCHAR(255),
    
    -- Contact
    primary_contact_email   VARCHAR(255) NOT NULL,
    primary_contact_phone   VARCHAR(50),
    billing_email           VARCHAR(255),
    
    -- Address
    address_line1           VARCHAR(255),
    address_line2           VARCHAR(255),
    city                    VARCHAR(100),
    state_province          VARCHAR(100),
    postal_code             VARCHAR(20),
    country                 CHAR(2),
    
    -- Subscription tier
    tier                    VARCHAR(20) DEFAULT 'STANDARD' CHECK (tier IN ('BASIC', 'STANDARD', 'PROFESSIONAL', 'ENTERPRISE')),
    
    -- Features and limits
    max_users               INTEGER DEFAULT 10,
    max_portfolios          INTEGER DEFAULT 5,
    max_data_sources        INTEGER DEFAULT 3,
    data_retention_days     INTEGER DEFAULT 365,
    
    -- Status
    status                  VARCHAR(15) DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'SUSPENDED', 'CANCELLED', 'PENDING')),
    
    -- Billing
    subscription_start      DATE,
    subscription_end        DATE,
    billing_cycle           VARCHAR(10) DEFAULT 'MONTHLY' CHECK (billing_cycle IN ('MONTHLY', 'QUARTERLY', 'ANNUAL')),
    
    -- Security
    mfa_required            BOOLEAN DEFAULT FALSE,
    sso_provider            VARCHAR(50),  -- SAML, OIDC provider
    sso_metadata_url        TEXT,
    allowed_domains         TEXT[],       -- Email domains for auto-provisioning
    
    -- Timestamps
    created_at              TIMESTAMPTZ DEFAULT NOW(),
    updated_at              TIMESTAMPTZ DEFAULT NOW(),
    
    -- Data isolation settings
    dedicated_schema        BOOLEAN DEFAULT FALSE,  -- If TRUE, tenant gets own schema
    schema_name             VARCHAR(63)  -- Name of dedicated schema if applicable
);

CREATE INDEX idx_tenants_status ON enterprise.tenants(status);
CREATE INDEX idx_tenants_tier ON enterprise.tenants(tier);
```

### 5.2 Users

```sql
-- User accounts with SSO support
CREATE TABLE enterprise.users (
    user_id                 BIGSERIAL PRIMARY KEY,
    tenant_id               BIGINT NOT NULL REFERENCES enterprise.tenants(tenant_id),
    
    -- Identification
    email                   VARCHAR(255) NOT NULL,
    username                VARCHAR(50),
    
    -- Profile
    first_name              VARCHAR(100) NOT NULL,
    last_name               VARCHAR(100) NOT NULL,
    display_name            VARCHAR(100),
    avatar_url              TEXT,
    
    -- Authentication
    password_hash           VARCHAR(255),  -- NULL for SSO-only users
    sso_subject_id          VARCHAR(255),  -- External ID from SSO provider
    auth_provider           VARCHAR(20) DEFAULT 'LOCAL' CHECK (auth_provider IN ('LOCAL', 'SAML', 'OIDC', 'LDAP')),
    
    -- MFA
    mfa_enabled             BOOLEAN DEFAULT FALSE,
    mfa_secret              VARCHAR(255),  -- Encrypted TOTP secret
    mfa_backup_codes        TEXT[],
    
    -- Status
    status                  VARCHAR(15) DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'INACTIVE', 'SUSPENDED', 'PENDING_VERIFICATION')),
    
    -- Role assignment (for simplified RBAC)
    default_role_id         BIGINT REFERENCES enterprise.roles(role_id),
    
    -- Preferences
    timezone                VARCHAR(50) DEFAULT 'America/New_York',
    locale                  VARCHAR(10) DEFAULT 'en-US',
    date_format             VARCHAR(20) DEFAULT 'MM/DD/YYYY',
    number_format           VARCHAR(20) DEFAULT '1,000.00',
    theme                   VARCHAR(10) DEFAULT 'LIGHT' CHECK (theme IN ('LIGHT', 'DARK', 'SYSTEM')),
    
    -- Trading entitlements
    can_trade               BOOLEAN DEFAULT FALSE,
    trading_limits          JSONB,  -- Per-asset class limits
    
    -- Session
    last_login_at           TIMESTAMPTZ,
    last_login_ip           INET,
    password_changed_at     TIMESTAMPTZ DEFAULT NOW(),
    password_expires_at     TIMESTAMPTZ,
    
    -- Security
    failed_login_attempts   INTEGER DEFAULT 0,
    locked_until            TIMESTAMPTZ,
    
    -- Timestamps
    created_at              TIMESTAMPTZ DEFAULT NOW(),
    updated_at              TIMESTAMPTZ DEFAULT NOW(),
    
    CONSTRAINT uq_tenant_email UNIQUE (tenant_id, email)
);

CREATE INDEX idx_users_tenant ON enterprise.users(tenant_id);
CREATE INDEX idx_users_email ON enterprise.users(email);
CREATE INDEX idx_users_status ON enterprise.users(status) WHERE status = 'ACTIVE';
CREATE INDEX idx_users_sso ON enterprise.users(sso_subject_id) WHERE sso_subject_id IS NOT NULL;
```

### 5.3 Teams

```sql
-- User teams for grouping and permissions
CREATE TABLE enterprise.teams (
    team_id                 BIGSERIAL PRIMARY KEY,
    tenant_id               BIGINT NOT NULL REFERENCES enterprise.tenants(tenant_id),
    
    team_name               VARCHAR(100) NOT NULL,
    description             TEXT,
    
    -- Team type
    team_type               VARCHAR(20) DEFAULT 'DEPARTMENT' CHECK (team_type IN (
        'DEPARTMENT', 'DESK', 'STRATEGY', 'PROJECT', 'CUSTOM'
    )),
    
    -- Hierarchy
    parent_team_id          BIGINT REFERENCES enterprise.teams(team_id),
    
    -- Manager
    manager_id              BIGINT REFERENCES enterprise.users(user_id),
    
    created_at              TIMESTAMPTZ DEFAULT NOW(),
    updated_at              TIMESTAMPTZ DEFAULT NOW(),
    
    CONSTRAINT uq_team_name_tenant UNIQUE (tenant_id, team_name)
);

-- Team memberships
CREATE TABLE enterprise.team_members (
    team_id                 BIGINT NOT NULL REFERENCES enterprise.teams(team_id) ON DELETE CASCADE,
    user_id                 BIGINT NOT NULL REFERENCES enterprise.users(user_id) ON DELETE CASCADE,
    
    role_in_team            VARCHAR(30) DEFAULT 'MEMBER' CHECK (role_in_team IN ('MEMBER', 'LEAD', 'ADMIN')),
    joined_at               TIMESTAMPTZ DEFAULT NOW(),
    
    PRIMARY KEY (team_id, user_id)
);
```

### 5.4 Roles & Permissions (RBAC)

```sql
-- Roles
CREATE TABLE enterprise.roles (
    role_id                 BIGSERIAL PRIMARY KEY,
    tenant_id               BIGINT REFERENCES enterprise.tenants(tenant_id),  -- NULL for global roles
    
    role_name               VARCHAR(50) NOT NULL,
    description             TEXT,
    
    -- Role type
    role_type               VARCHAR(20) DEFAULT 'CUSTOM' CHECK (role_type IN (
        'SYSTEM_ADMIN', 'TENANT_ADMIN', 'PORTFOLIO_MANAGER', 'TRADER', 
        'ANALYST', 'RISK_MANAGER', 'COMPLIANCE_OFFICER', 'VIEWER', 'CUSTOM'
    )),
    
    -- System roles cannot be modified
    is_system               BOOLEAN DEFAULT FALSE,
    
    created_at              TIMESTAMPTZ DEFAULT NOW(),
    
    CONSTRAINT uq_role_name_tenant UNIQUE (tenant_id, role_name)
);

-- Permissions catalog (master list of all permissions)
CREATE TABLE enterprise.permissions (
    permission_id           SERIAL PRIMARY KEY,
    permission_code         VARCHAR(50) NOT NULL UNIQUE,
    permission_name         VARCHAR(100) NOT NULL,
    description             TEXT,
    resource_type           VARCHAR(30) NOT NULL,  -- MARKET_DATA, TRADING, ANALYTICS, etc.
    action                  VARCHAR(20) NOT NULL   -- READ, WRITE, EXECUTE, DELETE, ADMIN
);

-- Role-Permission mapping
CREATE TABLE enterprise.role_permissions (
    role_id                 BIGINT NOT NULL REFERENCES enterprise.roles(role_id) ON DELETE CASCADE,
    permission_id           INTEGER NOT NULL REFERENCES enterprise.permissions(permission_id) ON DELETE CASCADE,
    
    -- Optional: Scope restrictions
    scope_type              VARCHAR(20),  -- ALL, OWN, TEAM, DEPARTMENT
    scope_expression        TEXT,         -- JSON logic for complex scoping
    
    granted_at              TIMESTAMPTZ DEFAULT NOW(),
    granted_by              BIGINT REFERENCES enterprise.users(user_id),
    
    PRIMARY KEY (role_id, permission_id)
);

-- User-Role assignments (many-to-many)
CREATE TABLE enterprise.user_roles (
    user_id                 BIGINT NOT NULL REFERENCES enterprise.users(user_id) ON DELETE CASCADE,
    role_id                 BIGINT NOT NULL REFERENCES enterprise.roles(role_id) ON DELETE CASCADE,
    
    -- Scope override
    portfolio_scope         BIGINT[],  -- Array of allowed portfolio IDs
    
    assigned_at             TIMESTAMPTZ DEFAULT NOW(),
    assigned_by             BIGINT REFERENCES enterprise.users(user_id),
    expires_at              TIMESTAMPTZ,
    
    PRIMARY KEY (user_id, role_id)
);

-- Insert default permissions
INSERT INTO enterprise.permissions (permission_code, permission_name, resource_type, action) VALUES
-- Market Data
('market_data.read_realtime', 'Read Real-time Market Data', 'MARKET_DATA', 'READ'),
('market_data.read_delayed', 'Read Delayed Market Data', 'MARKET_DATA', 'READ'),
('market_data.read_historical', 'Read Historical Market Data', 'MARKET_DATA', 'READ'),
('market_data.export', 'Export Market Data', 'MARKET_DATA', 'EXPORT'),

-- Trading
('trading.view_orders', 'View Orders', 'TRADING', 'READ'),
('trading.place_orders', 'Place Orders', 'TRADING', 'EXECUTE'),
('trading.cancel_orders', 'Cancel Orders', 'TRADING', 'WRITE'),
('trading.modify_orders', 'Modify Orders', 'TRADING', 'WRITE'),
('trading.view_blotter', 'View Transaction Blotter', 'TRADING', 'READ'),

-- Analytics
('analytics.view_portfolios', 'View Portfolios', 'ANALYTICS', 'READ'),
('analytics.manage_portfolios', 'Manage Portfolios', 'ANALYTICS', 'WRITE'),
('analytics.view_risk', 'View Risk Metrics', 'ANALYTICS', 'READ'),
('analytics.run_reports', 'Run Analytics Reports', 'ANALYTICS', 'EXECUTE'),

-- Research
('research.read', 'Read Research', 'RESEARCH', 'READ'),
('research.write', 'Write Research', 'RESEARCH', 'WRITE'),
('research.publish', 'Publish Research', 'RESEARCH', 'EXECUTE'),
('research.approve', 'Approve Research', 'RESEARCH', 'ADMIN'),

-- Admin
('admin.users', 'Manage Users', 'ADMIN', 'ADMIN'),
('admin.roles', 'Manage Roles', 'ADMIN', 'ADMIN'),
('admin.settings', 'Manage Settings', 'ADMIN', 'ADMIN'),
('admin.billing', 'Manage Billing', 'ADMIN', 'ADMIN');

-- Insert default system roles
INSERT INTO enterprise.roles (role_id, role_name, description, role_type, is_system) VALUES
(1, 'System Administrator', 'Full system access', 'SYSTEM_ADMIN', TRUE),
(2, 'Tenant Administrator', 'Full tenant administration', 'TENANT_ADMIN', TRUE),
(3, 'Portfolio Manager', 'Manage portfolios and view all analytics', 'PORTFOLIO_MANAGER', TRUE),
(4, 'Trader', 'Execute trades and manage orders', 'TRADER', TRUE),
(5, 'Analyst', 'Research and analysis capabilities', 'ANALYST', TRUE),
(6, 'Risk Manager', 'Risk oversight and monitoring', 'RISK_MANAGER', TRUE),
(7, 'Compliance Officer', 'Compliance monitoring and audit', 'COMPLIANCE_OFFICER', TRUE),
(8, 'Viewer', 'Read-only access', 'VIEWER', TRUE);
```

### 5.5 Sessions

```sql
-- Active user sessions
CREATE TABLE enterprise.sessions (
    session_id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id                 BIGINT NOT NULL REFERENCES enterprise.users(user_id) ON DELETE CASCADE,
    tenant_id               BIGINT NOT NULL REFERENCES enterprise.tenants(tenant_id),
    
    -- Session metadata
    device_type             VARCHAR(20),  -- DESKTOP, MOBILE, TABLET, API
    device_info             TEXT,
    ip_address              INET,
    user_agent              TEXT,
    
    -- Tokens
    refresh_token_hash      VARCHAR(255),
    
    -- Timing
    created_at              TIMESTAMPTZ DEFAULT NOW(),
    last_activity_at        TIMESTAMPTZ DEFAULT NOW(),
    expires_at              TIMESTAMPTZ NOT NULL,
    
    -- Status
    is_active               BOOLEAN DEFAULT TRUE,
    terminated_at           TIMESTAMPTZ,
    termination_reason      VARCHAR(20) CHECK (termination_reason IN ('LOGOUT', 'EXPIRED', 'REVOKED', 'SECURITY'))
);

CREATE INDEX idx_sessions_user ON enterprise.sessions(user_id, created_at DESC);
CREATE INDEX idx_sessions_active ON enterprise.sessions(is_active, expires_at) WHERE is_active = TRUE;
```

---

## 6. Audit Schema

### 6.1 Audit Logs (Immutable)

```sql
-- Comprehensive audit logging
CREATE TABLE audit.logs (
    log_id                  BIGSERIAL,
    tenant_id               BIGINT REFERENCES enterprise.tenants(tenant_id),
    
    -- Event classification
    event_type              VARCHAR(30) NOT NULL CHECK (event_type IN (
        'AUTH_LOGIN', 'AUTH_LOGOUT', 'AUTH_FAILED', 'AUTH_MFA',
        'USER_CREATE', 'USER_UPDATE', 'USER_DELETE', 'USER_DISABLE',
        'ORDER_CREATE', 'ORDER_MODIFY', 'ORDER_CANCEL', 'ORDER_EXECUTE',
        'PORTFOLIO_CREATE', 'PORTFOLIO_UPDATE', 'PORTFOLIO_DELETE',
        'DATA_EXPORT', 'DATA_ACCESS', 'PERMISSION_CHANGE',
        'SETTINGS_CHANGE', 'API_CALL', 'SYSTEM_EVENT'
    )),
    
    event_severity          VARCHAR(10) DEFAULT 'INFO' CHECK (event_severity IN ('DEBUG', 'INFO', 'WARN', 'ERROR', 'CRITICAL')),
    
    -- Actor
    user_id                 BIGINT REFERENCES enterprise.users(user_id),
    user_email              VARCHAR(255),  -- Denormalized for audit trail persistence
    session_id              UUID,
    api_key_id              VARCHAR(50),   -- For API access
    
    -- Resource being acted upon
    resource_type           VARCHAR(30),
    resource_id             VARCHAR(50),
    
    -- Action details
    action                  VARCHAR(50) NOT NULL,
    action_description      TEXT,
    
    -- Before/After values for changes
    before_values           JSONB,
    after_values            JSONB,
    
    -- Context
    ip_address              INET,
    user_agent              TEXT,
    geolocation             JSONB,  -- Country, city, etc.
    
    -- Compliance
    compliance_flag         VARCHAR(20),  -- For regulatory marking
    retention_class         VARCHAR(10) DEFAULT 'STANDARD' CHECK (retention_class IN ('STANDARD', 'EXTENDED', 'PERMANENT')),
    
    -- Immutable timestamp
    occurred_at             TIMESTAMPTZ NOT NULL,
    
    -- Hash chain for tamper detection (optional blockchain-style verification)
    previous_hash           VARCHAR(64),
    current_hash            VARCHAR(64) GENERATED ALWAYS AS (
        encode(digest(
            event_type::text || occurred_at::text || COALESCE(user_id::text, '') || COALESCE(action, ''),
            'sha256'
        ), 'hex')
    ) STORED,
    
    PRIMARY KEY (log_id, occurred_at)
);

SELECT create_hypertable(
    'audit.logs',
    'occurred_at',
    chunk_time_interval => INTERVAL '1 month',
    if_not_exists => TRUE
);

SELECT add_dimension('audit.logs', 'tenant_id', number_partitions => 4);

-- Critical indexes for audit queries
CREATE INDEX idx_audit_tenant ON audit.logs(tenant_id, occurred_at DESC);
CREATE INDEX idx_audit_user ON audit.logs(user_id, occurred_at DESC);
CREATE INDEX idx_audit_event ON audit.logs(event_type, occurred_at DESC);
CREATE INDEX idx_audit_resource ON audit.logs(resource_type, resource_id, occurred_at DESC);
CREATE INDEX idx_audit_severity ON audit.logs(event_severity, occurred_at DESC) WHERE event_severity IN ('ERROR', 'CRITICAL');

-- Compression - audit logs are rarely modified after creation
ALTER TABLE audit.logs SET (timescaledb.compress);
SELECT add_compression_policy('audit.logs', INTERVAL '7 days');

-- Extended retention for compliance
SELECT add_retention_policy('audit.logs', INTERVAL '10 years');
```

### 6.2 Compliance Rules

```sql
-- Compliance monitoring rules
CREATE TABLE compliance.rules (
    rule_id                 BIGSERIAL PRIMARY KEY,
    tenant_id               BIGINT NOT NULL REFERENCES enterprise.tenants(tenant_id),
    
    -- Rule definition
    rule_name               VARCHAR(100) NOT NULL,
    rule_description        TEXT,
    rule_type               VARCHAR(30) NOT NULL CHECK (rule_type IN (
        'POSITION_LIMIT', 'CONCENTRATION_LIMIT', 'TRADING_RESTRICTION',
        'GATEWAY_LIMIT', 'CUSTODY_RESTRICTION', 'REGULATORY_REPORTING',
        'PRE_TRADE_CHECK', 'POST_TRADE_CHECK'
    )),
    
    -- Regulatory framework
    regulatory_framework    VARCHAR(30),  -- SEC, FINRA, FCA, MiFID, etc.
    rule_code               VARCHAR(50),  -- Internal or external rule code
    
    -- Rule logic (stored as JSON for flexibility)
    rule_definition         JSONB NOT NULL,
    -- Example definitions:
    -- Position limit: {"asset_class": "EQUITY", "max_notional": 10000000, "scope": "PORTFOLIO"}
    -- Concentration: {"max_pct_of_portfolio": 0.05, "scope": "SINGLE_SECURITY"}
    -- Trading restriction: {"restricted_symbols": ["XYZ"], "restriction_type": "SHORT_SALE"}
    
    -- Enforcement
    enforcement_level       VARCHAR(15) DEFAULT 'WARNING' CHECK (enforcement_level IN ('WARNING', 'REQUIRE_APPROVAL', 'BLOCK', 'ALERT_ONLY')),
    approver_roles          BIGINT[],     -- Roles that can override
    
    -- Scope
    applies_to_portfolios   BIGINT[],     -- NULL = all portfolios
    applies_to_users        BIGINT[],     -- NULL = all users
    applies_to_instruments  BIGINT[],     -- NULL = all instruments
    
    -- Status
    status                  VARCHAR(10) DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'INACTIVE', 'DRAFT')),
    effective_date          DATE NOT NULL,
    expiration_date         DATE,
    
    -- Breach tracking
    breach_count_30d        INTEGER DEFAULT 0,
    last_breach_at          TIMESTAMPTZ,
    
    -- Metadata
    created_by              BIGINT NOT NULL REFERENCES enterprise.users(user_id),
    created_at              TIMESTAMPTZ DEFAULT NOW(),
    updated_at              TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_compliance_rules_tenant ON compliance.rules(tenant_id, status);
CREATE INDEX idx_compliance_rules_type ON compliance.rules(rule_type);

-- Compliance breaches
CREATE TABLE compliance.breaches (
    breach_id               BIGSERIAL,
    tenant_id               BIGINT NOT NULL REFERENCES enterprise.tenants(tenant_id),
    rule_id                 BIGINT NOT NULL REFERENCES compliance.rules(rule_id),
    
    -- Breach details
    occurred_at             TIMESTAMPTZ NOT NULL,
    detected_at             TIMESTAMPTZ DEFAULT NOW(),
    
    -- Entity that breached
    portfolio_id            BIGINT REFERENCES analytics.portfolios(portfolio_id),
    user_id                 BIGINT REFERENCES enterprise.users(user_id),
    instrument_id           BIGINT REFERENCES ref_data.instruments(instrument_id),
    order_id                BIGINT REFERENCES trading.orders(order_id),
    
    -- Breach data
    breach_value            DECIMAL(18, 4),  -- The value that breached the limit
    limit_value             DECIMAL(18, 4),  -- The limit that was breached
    breach_description      TEXT,
    
    -- Resolution
    status                  VARCHAR(15) DEFAULT 'OPEN' CHECK (status IN ('OPEN', 'UNDER_REVIEW', 'APPROVED', 'RESOLVED', 'ESCALATED')),
    resolution              TEXT,
    resolved_by             BIGINT REFERENCES enterprise.users(user_id),
    resolved_at             TIMESTAMPTZ,
    
    -- Workflow
    assigned_to             BIGINT REFERENCES enterprise.users(user_id),
    
    PRIMARY KEY (breach_id, occurred_at)
);

SELECT create_hypertable(
    'compliance.breaches',
    'occurred_at',
    chunk_time_interval => INTERVAL '1 year',
    if_not_exists => TRUE
);

CREATE INDEX idx_breaches_tenant ON compliance.breaches(tenant_id, occurred_at DESC);
CREATE INDEX idx_breaches_rule ON compliance.breaches(rule_id, occurred_at DESC);
CREATE INDEX idx_breaches_status ON compliance.breaches(status) WHERE status = 'OPEN';
```

---

## 7. Views and Functions

### 7.1 Common Views

```sql
-- Current portfolio positions (flattened from temporal table)
CREATE OR REPLACE VIEW analytics.current_holdings AS
SELECT DISTINCT ON (tenant_id, portfolio_id, instrument_id)
    tenant_id,
    portfolio_id,
    instrument_id,
    quantity,
    avg_cost_basis,
    total_cost_basis,
    market_price,
    market_value,
    unrealized_pnl,
    valid_from,
    as_of_date
FROM analytics.holdings
WHERE valid_to IS NULL
ORDER BY tenant_id, portfolio_id, instrument_id, valid_from DESC;

-- Order book view with instrument details
CREATE OR REPLACE VIEW trading.order_book_view AS
SELECT 
    o.*,
    i.symbol,
    i.exchange_code,
    i.asset_class,
    u.first_name || ' ' || u.last_name as trader_name,
    p.portfolio_name
FROM trading.orders o
JOIN ref_data.instruments i ON o.instrument_id = i.instrument_id
JOIN enterprise.users u ON o.created_by = u.user_id
JOIN analytics.portfolios p ON o.portfolio_id = p.portfolio_id;

-- Portfolio performance summary
CREATE OR REPLACE VIEW analytics.portfolio_summary AS
SELECT 
    p.portfolio_id,
    p.tenant_id,
    p.portfolio_name,
    p.portfolio_code,
    p.base_currency,
    p.status,
    
    -- Latest holdings
    COUNT(DISTINCT h.instrument_id) as num_positions,
    COALESCE(SUM(h.market_value), 0) as total_market_value,
    COALESCE(SUM(h.unrealized_pnl), 0) as total_unrealized_pnl,
    
    -- Latest risk metrics
    rm.var_95_1d,
    rm.realized_vol_30d,
    rm.max_drawdown_current,
    
    -- Latest returns
    r.mtd_return,
    r.ytd_return
    
FROM analytics.portfolios p
LEFT JOIN analytics.current_holdings h ON p.portfolio_id = h.portfolio_id
LEFT JOIN LATERAL (
    SELECT * FROM analytics.risk_metrics 
    WHERE entity_type = 'PORTFOLIO' 
    AND entity_id = p.portfolio_id 
    ORDER BY calculation_date DESC 
    LIMIT 1
) rm ON true
LEFT JOIN LATERAL (
    SELECT * FROM analytics.returns 
    WHERE entity_type = 'PORTFOLIO' 
    AND entity_id = p.portfolio_id 
    ORDER BY date DESC 
    LIMIT 1
) r ON true
WHERE p.status = 'ACTIVE'
GROUP BY p.portfolio_id, rm.var_95_1d, rm.realized_vol_30d, rm.max_drawdown_current, r.mtd_return, r.ytd_return;
```

### 7.2 Utility Functions

```sql
-- Get current portfolio value
CREATE OR REPLACE FUNCTION analytics.get_portfolio_value(p_portfolio_id BIGINT, p_as_of_date DATE DEFAULT CURRENT_DATE)
RETURNS DECIMAL(18, 2) AS $$
DECLARE
    v_value DECIMAL(18, 2);
BEGIN
    SELECT COALESCE(SUM(market_value), 0)
    INTO v_value
    FROM analytics.holdings
    WHERE portfolio_id = p_portfolio_id
    AND as_of_date = p_as_of_date
    AND valid_to IS NULL;
    
    RETURN v_value;
END;
$$ LANGUAGE plpgsql STABLE;

-- Calculate portfolio return for period
CREATE OR REPLACE FUNCTION analytics.calculate_return(
    p_portfolio_id BIGINT,
    p_start_date DATE,
    p_end_date DATE
) RETURNS DECIMAL(12, 8) AS $$
DECLARE
    v_start_value DECIMAL(18, 2);
    v_end_value DECIMAL(18, 2);
    v_net_flows DECIMAL(18, 2);
BEGIN
    -- Get start value
    SELECT COALESCE(SUM(market_value), 0)
    INTO v_start_value
    FROM analytics.holdings
    WHERE portfolio_id = p_portfolio_id
    AND as_of_date = p_start_date
    AND valid_to IS NULL;
    
    -- Get end value
    SELECT COALESCE(SUM(market_value), 0)
    INTO v_end_value
    FROM analytics.holdings
    WHERE portfolio_id = p_portfolio_id
    AND as_of_date = p_end_date
    AND valid_to IS NULL;
    
    -- Get net flows (contributions/withdrawals)
    SELECT COALESCE(SUM(CASE 
        WHEN transaction_type IN ('TRANSFER_IN', 'CASH_DIVIDEND') THEN net_amount
        WHEN transaction_type IN ('TRANSFER_OUT') THEN -net_amount
        ELSE 0
    END), 0)
    INTO v_net_flows
    FROM trading.blotter
    WHERE portfolio_id = p_portfolio_id
    AND trade_date > p_start_date
    AND trade_date <= p_end_date;
    
    -- Time-weighted return
    RETURN (v_end_value - v_start_value - v_net_flows) / NULLIF(v_start_value, 0);
END;
$$ LANGUAGE plpgsql STABLE;

-- Check user permission
CREATE OR REPLACE FUNCTION enterprise.has_permission(
    p_user_id BIGINT,
    p_permission_code VARCHAR(50),
    p_resource_type VARCHAR(30) DEFAULT NULL,
    p_resource_id VARCHAR(50) DEFAULT NULL
) RETURNS BOOLEAN AS $$
DECLARE
    v_has_permission BOOLEAN;
BEGIN
    SELECT EXISTS (
        SELECT 1
        FROM enterprise.user_roles ur
        JOIN enterprise.role_permissions rp ON ur.role_id = rp.role_id
        JOIN enterprise.permissions p ON rp.permission_id = p.permission_id
        WHERE ur.user_id = p_user_id
        AND (ur.expires_at IS NULL OR ur.expires_at > NOW())
        AND p.permission_code = p_permission_code
    )
    INTO v_has_permission;
    
    RETURN v_has_permission;
END;
$$ LANGUAGE plpgsql STABLE;
```

---

## 8. Row-Level Security (RLS) Policies

```sql
-- Enable RLS on tenant-isolated tables
ALTER TABLE analytics.portfolios ENABLE ROW LEVEL SECURITY;
ALTER TABLE analytics.holdings ENABLE ROW LEVEL SECURITY;
ALTER TABLE analytics.risk_metrics ENABLE ROW LEVEL SECURITY;
ALTER TABLE trading.orders ENABLE ROW LEVEL SECURITY;
ALTER TABLE trading.blotter ENABLE ROW LEVEL SECURITY;
ALTER TABLE research.notes ENABLE ROW LEVEL SECURITY;
ALTER TABLE research.watchlists ENABLE ROW LEVEL SECURITY;

-- RLS Policy: Users can only see their tenant's data
CREATE POLICY tenant_isolation ON analytics.portfolios
    USING (tenant_id = current_setting('app.current_tenant_id')::BIGINT);

CREATE POLICY tenant_isolation ON analytics.holdings
    USING (tenant_id = current_setting('app.current_tenant_id')::BIGINT);

CREATE POLICY tenant_isolation ON trading.orders
    USING (tenant_id = current_setting('app.current_tenant_id')::BIGINT);

-- RLS Policy: Research notes visibility
CREATE POLICY note_visibility ON research.notes
    USING (
        tenant_id = current_setting('app.current_tenant_id')::BIGINT
        AND (
            author_id = current_setting('app.current_user_id')::BIGINT
            OR visibility = 'FIRM'
            OR (visibility = 'TEAM' AND EXISTS (
                SELECT 1 FROM enterprise.team_members 
                WHERE user_id = current_setting('app.current_user_id')::BIGINT
            ))
        )
    );
```

---

## 9. Data Retention Summary

| Table/Schema | Retention | Compression | Notes |
|--------------|-----------|-------------|-------|
| `market_data.ticks` | 7 years | After 7 days | Aggressive compression for ticks |
| `market_data.quotes` | 2 years | After 3 days | L1 quote data |
| `market_data.order_book` | 90 days | After 1 day | L2 depth, shorter retention |
| `market_data.bars` | 10 years | After 30 days | OHLCV data |
| `analytics.holdings` | 10 years | After 90 days | Daily snapshots |
| `analytics.risk_metrics` | 10 years | After 30 days | Calculated metrics |
| `analytics.option_greeks` | 3 years | After 7 days | Intraday calculations |
| `trading.blotter` | 10 years | After 30 days | Regulatory requirement |
| `audit.logs` | 10 years | After 7 days | Compliance, immutable |
| `compliance.breaches` | 10 years | - | Regulatory requirement |

---

## 10. Maintenance Procedures

```sql
-- Analyze all tables
CREATE OR REPLACE PROCEDURE maintenance.analyze_all()
LANGUAGE plpgsql AS $$
BEGIN
    ANALYZE market_data.ticks;
    ANALYZE market_data.quotes;
    ANALYZE market_data.bars;
    ANALYZE analytics.holdings;
    ANALYZE trading.blotter;
    ANALYZE audit.logs;
END;
$$;

-- Reindex hypertables (run during maintenance window)
CREATE OR REPLACE PROCEDURE maintenance.reindex_hypertables()
LANGUAGE plpgsql AS $$
BEGIN
    REINDEX TABLE CONCURRENTLY market_data.ticks;
    REINDEX TABLE CONCURRENTLY market_data.quotes;
    REINDEX TABLE CONCURRENTLY market_data.bars;
END;
$$;

-- Vacuum and freeze old data
CREATE OR REPLACE PROCEDURE maintenance.vintage_freeze(
    p_table_name TEXT,
    p_before_date DATE
)
LANGUAGE plpgsql AS $$
BEGIN
    EXECUTE format(
        'VACUUM FREEZE %I WHERE ts < %L',
        p_table_name,
        p_before_date
    );
END;
$$;
```

---

## 11. Connection Pooling Recommendations

For PgBouncer or similar connection poolers:

```ini
; PgBouncer configuration for DragonScope Enterprise
[databases]
dragonscope = host=localhost port=5432 dbname=dragonscope

[pgbouncer]
listen_port = 6432
listen_addr = 0.0.0.0
auth_type = md5

; Pool settings
pool_mode = transaction
max_client_conn = 10000
default_pool_size = 25
min_pool_size = 5
reserve_pool_size = 5
reserve_pool_timeout = 3

; Timeouts
server_idle_timeout = 600
server_lifetime = 3600
server_connect_timeout = 15
query_timeout = 300
query_wait_timeout = 120

; TimeScaleDB-specific: Use transaction pooling for continuous aggregates
; Session pooling only if using temporary tables extensively
```

---

## 12. Hardware Sizing Guidelines

| Component | Small (< 10 users) | Medium (10-100 users) | Large (100-1000 users) | Enterprise (1000+) |
|-----------|-------------------|----------------------|----------------------|-------------------|
| **CPU Cores** | 8 | 16-32 | 32-64 | 64+ |
| **RAM** | 32 GB | 128 GB | 256 GB | 512 GB+ |
| **Storage** | 1 TB SSD | 5 TB NVMe | 20 TB NVMe | 100 TB+ tiered |
| **Network** | 1 Gbps | 10 Gbps | 25 Gbps | 100 Gbps |
| **TimescaleDB** | Single node | Single node | Multi-node | Distributed |

---

*Schema Version: 1.0.0*  
*Last Updated: 2026-02-28*  
*Compatible with: PostgreSQL 16+, TimescaleDB 2.13+*
