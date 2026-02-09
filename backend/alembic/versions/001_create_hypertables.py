"""Create TimescaleDB hypertables for market data

Revision ID: 001_hypertables
Revises:
Create Date: 2026-02-09
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "001_hypertables"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── market_ticks ────────────────────────────────────────────────
    op.create_table(
        "market_ticks",
        sa.Column("time", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("symbol", sa.String(32), nullable=False),
        sa.Column("category", sa.String(16), nullable=False),
        sa.Column("price", sa.Double, nullable=True),
        sa.Column("open", sa.Double, nullable=True),
        sa.Column("high", sa.Double, nullable=True),
        sa.Column("low", sa.Double, nullable=True),
        sa.Column("volume", sa.Double, nullable=True),
        sa.Column("market_cap", sa.Double, nullable=True),
        sa.Column("change_pct", sa.Double, nullable=True),
        sa.Column("extra", JSONB, nullable=True),
        sa.PrimaryKeyConstraint("time", "symbol"),
    )

    # ── snapshot_logs ───────────────────────────────────────────────
    op.create_table(
        "snapshot_logs",
        sa.Column("time", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("category", sa.String(32), nullable=False),
        sa.Column("snapshot", JSONB, nullable=False),
        sa.Column("record_count", sa.Integer, nullable=True),
        sa.PrimaryKeyConstraint("time", "category"),
    )

    # ── Convert to hypertables ──────────────────────────────────────
    op.execute("SELECT create_hypertable('market_ticks', 'time', chunk_time_interval => INTERVAL '1 day')")
    op.execute("SELECT create_hypertable('snapshot_logs', 'time', chunk_time_interval => INTERVAL '7 days')")

    # ── Indexes ─────────────────────────────────────────────────────
    op.create_index(
        "ix_market_ticks_category_symbol_time",
        "market_ticks",
        ["category", "symbol", sa.text("time DESC")],
    )
    op.create_index(
        "ix_snapshot_logs_category_time",
        "snapshot_logs",
        ["category", sa.text("time DESC")],
    )

    # ── Continuous aggregates ───────────────────────────────────────
    # 1-hour OHLCV buckets
    op.execute("""
        CREATE MATERIALIZED VIEW market_ticks_1h
        WITH (timescaledb.continuous) AS
        SELECT
            time_bucket('1 hour', time) AS bucket,
            symbol,
            category,
            first(price, time)  AS open,
            max(price)          AS high,
            min(price)          AS low,
            last(price, time)   AS close,
            sum(volume)         AS volume,
            last(market_cap, time) AS market_cap,
            count(*)            AS tick_count
        FROM market_ticks
        GROUP BY bucket, symbol, category
        WITH NO DATA
    """)

    # 1-day OHLCV buckets
    op.execute("""
        CREATE MATERIALIZED VIEW market_ticks_1d
        WITH (timescaledb.continuous) AS
        SELECT
            time_bucket('1 day', time) AS bucket,
            symbol,
            category,
            first(price, time)  AS open,
            max(price)          AS high,
            min(price)          AS low,
            last(price, time)   AS close,
            sum(volume)         AS volume,
            last(market_cap, time) AS market_cap,
            count(*)            AS tick_count
        FROM market_ticks
        GROUP BY bucket, symbol, category
        WITH NO DATA
    """)

    # 1-week OHLCV buckets
    op.execute("""
        CREATE MATERIALIZED VIEW market_ticks_1w
        WITH (timescaledb.continuous) AS
        SELECT
            time_bucket('1 week', time) AS bucket,
            symbol,
            category,
            first(price, time)  AS open,
            max(price)          AS high,
            min(price)          AS low,
            last(price, time)   AS close,
            sum(volume)         AS volume,
            last(market_cap, time) AS market_cap,
            count(*)            AS tick_count
        FROM market_ticks
        GROUP BY bucket, symbol, category
        WITH NO DATA
    """)

    # ── Refresh policies for continuous aggregates ──────────────────
    op.execute("""
        SELECT add_continuous_aggregate_policy('market_ticks_1h',
            start_offset    => INTERVAL '3 hours',
            end_offset      => INTERVAL '1 hour',
            schedule_interval => INTERVAL '1 hour')
    """)
    op.execute("""
        SELECT add_continuous_aggregate_policy('market_ticks_1d',
            start_offset    => INTERVAL '3 days',
            end_offset      => INTERVAL '1 day',
            schedule_interval => INTERVAL '1 day')
    """)
    op.execute("""
        SELECT add_continuous_aggregate_policy('market_ticks_1w',
            start_offset    => INTERVAL '3 weeks',
            end_offset      => INTERVAL '1 week',
            schedule_interval => INTERVAL '1 week')
    """)

    # ── Compression policy (raw data) ──────────────────────────────
    op.execute("ALTER TABLE market_ticks SET (timescaledb.compress, timescaledb.compress_segmentby = 'symbol,category')")
    op.execute("SELECT add_compression_policy('market_ticks', INTERVAL '7 days')")

    op.execute("ALTER TABLE snapshot_logs SET (timescaledb.compress, timescaledb.compress_segmentby = 'category')")
    op.execute("SELECT add_compression_policy('snapshot_logs', INTERVAL '7 days')")

    # ── Retention policy (drop raw chunks older than 90 days) ──────
    op.execute("SELECT add_retention_policy('market_ticks', INTERVAL '90 days')")
    op.execute("SELECT add_retention_policy('snapshot_logs', INTERVAL '90 days')")


def downgrade() -> None:
    # Remove policies first (silently ignore if not found)
    op.execute("SELECT remove_retention_policy('market_ticks', if_exists => true)")
    op.execute("SELECT remove_retention_policy('snapshot_logs', if_exists => true)")
    op.execute("SELECT remove_compression_policy('market_ticks', if_exists => true)")
    op.execute("SELECT remove_compression_policy('snapshot_logs', if_exists => true)")

    # Drop continuous aggregates
    op.execute("DROP MATERIALIZED VIEW IF EXISTS market_ticks_1w CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS market_ticks_1d CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS market_ticks_1h CASCADE")

    # Drop hypertables (cascades chunks)
    op.drop_table("snapshot_logs")
    op.drop_table("market_ticks")
