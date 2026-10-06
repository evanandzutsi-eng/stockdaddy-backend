-- =========================================================================
-- NGX INTELLIGENCE TERMINAL - DATABASE INITIALIZATION SCRIPT
-- =========================================================================
-- This script must be executed against the PostgreSQL/TimescaleDB instance 
-- after the initial SQLAlchemy migrations have created the base tables.
-- It activates TimescaleDB hypertables and enforces Row-Level Security (RLS).
-- =========================================================================

-- 1. ENABLE TIMESCALEDB EXTENSION & HYPERTABLES
-- --------------------------------------------------------------------------
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'timescaledb') THEN
        CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;
    END IF;
END $$;

-- Converts the standard 'stock_ticks' table into a high-performance 
-- TimescaleDB hypertable partitioned by time.
SELECT create_hypertable('stock_ticks', 'timestamp', if_not_exists => TRUE);

-- Create continuous aggregates for real-time charting offloading
-- (e.g., 1-minute candles for the 1D chart view)
CREATE MATERIALIZED VIEW IF NOT EXISTS stock_ticks_1m
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 minute', timestamp) AS bucket,
    symbol,
    first(open_price, timestamp) AS open,
    max(high_price) AS high,
    min(low_price) AS low,
    last(close_price, timestamp) AS close,
    sum(volume) AS volume
FROM stock_ticks
GROUP BY bucket, symbol
WITH NO DATA;

-- Add continuous aggregate policy to refresh every 1 minute
SELECT add_continuous_aggregate_policy('stock_ticks_1m',
    start_offset => INTERVAL '1 hour',
    end_offset => INTERVAL '1 minute',
    schedule_interval => INTERVAL '1 minute',
    if_not_exists => TRUE);


-- 2. ENFORCE ROW-LEVEL SECURITY (RLS)
-- --------------------------------------------------------------------------
-- Mandate: RLS is active across all schemas to ensure strict data isolation.
-- Even if the application layer has a bug, the database will prevent 
-- cross-tenant data leakage.

-- Enable RLS on all core tables
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE simulation_portfolios ENABLE ROW LEVEL SECURITY;
ALTER TABLE simulation_holdings ENABLE ROW LEVEL SECURITY;
ALTER TABLE simulation_trades ENABLE ROW LEVEL SECURITY;
ALTER TABLE social_posts ENABLE ROW LEVEL SECURITY;
ALTER TABLE social_comments ENABLE ROW LEVEL SECURITY;

-- Note: The FastAPI backend must set the session variable 
-- 'app.current_user_id' on every database connection.

-- USERS: Users can only see their own profile
CREATE POLICY user_isolation ON users
    FOR ALL
    USING (id = current_setting('app.current_user_id', true)::uuid);

-- PORTFOLIOS: Users can only see their own virtual portfolio
CREATE POLICY portfolio_isolation ON simulation_portfolios
    FOR ALL
    USING (user_id = current_setting('app.current_user_id', true)::uuid);

-- HOLDINGS: Accessible only via the user's portfolio
CREATE POLICY holdings_isolation ON simulation_holdings
    FOR ALL
    USING (portfolio_id IN (
        SELECT id FROM simulation_portfolios 
        WHERE user_id = current_setting('app.current_user_id', true)::uuid
    ));

-- TRADES: Accessible only via the user's portfolio
CREATE POLICY trades_isolation ON simulation_trades
    FOR ALL
    USING (portfolio_id IN (
        SELECT id FROM simulation_portfolios 
        WHERE user_id = current_setting('app.current_user_id', true)::uuid
    ));

-- SOCIAL POSTS: Public read access for visible posts, but strict write/update 
-- isolation. Users can only edit/delete their own posts.
CREATE POLICY social_posts_read ON social_posts
    FOR SELECT
    USING (is_visible = TRUE);

CREATE POLICY social_posts_write ON social_posts
    FOR INSERT
    WITH CHECK (user_id = current_setting('app.current_user_id', true)::uuid);

CREATE POLICY social_posts_modify ON social_posts
    FOR UPDATE
    USING (user_id = current_setting('app.current_user_id', true)::uuid);

CREATE POLICY social_posts_delete ON social_posts
    FOR DELETE
    USING (user_id = current_setting('app.current_user_id', true)::uuid);

-- SOCIAL COMMENTS: Similar isolation
CREATE POLICY social_comments_read ON social_comments
    FOR SELECT
    USING (is_visible = TRUE);

CREATE POLICY social_comments_write ON social_comments
    FOR INSERT
    WITH CHECK (user_id = current_setting('app.current_user_id', true)::uuid);

CREATE POLICY social_comments_modify ON social_comments
    FOR UPDATE
    USING (user_id = current_setting('app.current_user_id', true)::uuid);

CREATE POLICY social_comments_delete ON social_comments
    FOR DELETE
    USING (user_id = current_setting('app.current_user_id', true)::uuid);

-- =========================================================================
-- END OF INITIALIZATION SCRIPT
-- =========================================================================