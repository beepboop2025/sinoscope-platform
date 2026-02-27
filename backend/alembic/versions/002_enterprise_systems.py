"""Create enterprise system tables

Revision ID: a2b3c4d5e6f7
Revises: 001_hypertables
Create Date: 2026-02-18
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, ARRAY

revision: str = "a2b3c4d5e6f7"
down_revision: Union[str, None] = "001_hypertables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ══════════════════════════════════════════════════════════════════
    # RBAC
    # ══════════════════════════════════════════════════════════════════
    op.create_table(
        "roles",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(64), nullable=False, unique=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("permissions", JSONB, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # ══════════════════════════════════════════════════════════════════
    # Quant Analytics
    # ══════════════════════════════════════════════════════════════════
    op.create_table(
        "yield_curves",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("curve_date", sa.Date, nullable=False),
        sa.Column("currency", sa.String(8), nullable=False, server_default="USD"),
        sa.Column("tenors", JSONB, nullable=False),
        sa.Column("rates", JSONB, nullable=False),
        sa.Column("curve_type", sa.String(32), nullable=False, server_default="spot"),
        sa.Column("source", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_yield_curves_date_currency", "yield_curves", ["curve_date", "currency"])

    op.create_table(
        "option_chains",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("symbol", sa.String(32), nullable=False),
        sa.Column("expiry", sa.Date, nullable=False),
        sa.Column("strike", sa.Double, nullable=False),
        sa.Column("option_type", sa.String(4), nullable=False),
        sa.Column("bid", sa.Double, nullable=True),
        sa.Column("ask", sa.Double, nullable=True),
        sa.Column("last", sa.Double, nullable=True),
        sa.Column("volume", sa.Integer, nullable=True),
        sa.Column("open_interest", sa.Integer, nullable=True),
        sa.Column("implied_vol", sa.Double, nullable=True),
        sa.Column("delta", sa.Double, nullable=True),
        sa.Column("gamma", sa.Double, nullable=True),
        sa.Column("theta", sa.Double, nullable=True),
        sa.Column("vega", sa.Double, nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_option_chains_symbol_expiry", "option_chains", ["symbol", "expiry"])

    op.create_table(
        "var_results",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("portfolio_id", sa.Integer, nullable=True),
        sa.Column("calc_date", sa.Date, nullable=False),
        sa.Column("method", sa.String(32), nullable=False),
        sa.Column("confidence_level", sa.Double, nullable=False),
        sa.Column("horizon_days", sa.Integer, nullable=False),
        sa.Column("var_value", sa.Double, nullable=False),
        sa.Column("cvar_value", sa.Double, nullable=True),
        sa.Column("parameters", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_var_results_portfolio_date", "var_results", ["portfolio_id", "calc_date"])

    op.create_table(
        "covariance_matrices",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("calc_date", sa.Date, nullable=False),
        sa.Column("symbols", JSONB, nullable=False),
        sa.Column("matrix", JSONB, nullable=False),
        sa.Column("method", sa.String(32), nullable=False, server_default="sample"),
        sa.Column("lookback_days", sa.Integer, nullable=False, server_default="252"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_covariance_matrices_date", "covariance_matrices", ["calc_date"])

    # ══════════════════════════════════════════════════════════════════
    # Backtesting
    # ══════════════════════════════════════════════════════════════════
    op.create_table(
        "strategies",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("strategy_type", sa.String(32), nullable=False),
        sa.Column("parameters", JSONB, nullable=False, server_default="{}"),
        sa.Column("code_hash", sa.String(64), nullable=True),
        sa.Column("user_id", sa.String(128), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "backtest_runs",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("strategy_id", sa.Integer, sa.ForeignKey("strategies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("start_date", sa.Date, nullable=False),
        sa.Column("end_date", sa.Date, nullable=False),
        sa.Column("initial_capital", sa.Double, nullable=False),
        sa.Column("final_value", sa.Double, nullable=True),
        sa.Column("total_return", sa.Double, nullable=True),
        sa.Column("sharpe_ratio", sa.Double, nullable=True),
        sa.Column("max_drawdown", sa.Double, nullable=True),
        sa.Column("win_rate", sa.Double, nullable=True),
        sa.Column("total_trades", sa.Integer, nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("parameters", JSONB, nullable=True),
        sa.Column("metrics", JSONB, nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_backtest_runs_strategy", "backtest_runs", ["strategy_id"])

    op.create_table(
        "backtest_trades",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.Integer, sa.ForeignKey("backtest_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("symbol", sa.String(32), nullable=False),
        sa.Column("side", sa.String(4), nullable=False),
        sa.Column("quantity", sa.Double, nullable=False),
        sa.Column("price", sa.Double, nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("commission", sa.Double, nullable=True, server_default="0"),
        sa.Column("slippage", sa.Double, nullable=True, server_default="0"),
        sa.Column("pnl", sa.Double, nullable=True),
        sa.Column("signal", sa.String(32), nullable=True),
        sa.Column("metadata", JSONB, nullable=True),
    )
    op.create_index("ix_backtest_trades_run", "backtest_trades", ["run_id"])

    # ══════════════════════════════════════════════════════════════════
    # NLP / Market Briefings
    # ══════════════════════════════════════════════════════════════════
    op.create_table(
        "nlp_documents",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("source", sa.String(64), nullable=False),
        sa.Column("doc_type", sa.String(32), nullable=False),
        sa.Column("title", sa.Text, nullable=True),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("url", sa.Text, nullable=True),
        sa.Column("symbols", JSONB, nullable=True),
        sa.Column("sentiment_score", sa.Double, nullable=True),
        sa.Column("sentiment_label", sa.String(16), nullable=True),
        sa.Column("entities", JSONB, nullable=True),
        sa.Column("topics", JSONB, nullable=True),
        sa.Column("summary", sa.Text, nullable=True),
        sa.Column("embedding_vector", JSONB, nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_nlp_documents_source_type", "nlp_documents", ["source", "doc_type"])

    op.create_table(
        "market_briefings",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("briefing_date", sa.Date, nullable=False),
        sa.Column("briefing_type", sa.String(32), nullable=False, server_default="daily"),
        sa.Column("title", sa.String(256), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("highlights", JSONB, nullable=True),
        sa.Column("market_summary", JSONB, nullable=True),
        sa.Column("generated_by", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_market_briefings_date", "market_briefings", ["briefing_date"])

    # ══════════════════════════════════════════════════════════════════
    # Alternative Data
    # ══════════════════════════════════════════════════════════════════
    op.create_table(
        "insider_trades",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("symbol", sa.String(32), nullable=False),
        sa.Column("filer_name", sa.String(256), nullable=False),
        sa.Column("filer_title", sa.String(128), nullable=True),
        sa.Column("transaction_type", sa.String(32), nullable=False),
        sa.Column("shares", sa.Double, nullable=False),
        sa.Column("price_per_share", sa.Double, nullable=True),
        sa.Column("total_value", sa.Double, nullable=True),
        sa.Column("filing_date", sa.Date, nullable=False),
        sa.Column("transaction_date", sa.Date, nullable=True),
        sa.Column("sec_url", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_insider_trades_symbol_date", "insider_trades", ["symbol", "filing_date"])

    op.create_table(
        "short_interests",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("symbol", sa.String(32), nullable=False),
        sa.Column("report_date", sa.Date, nullable=False),
        sa.Column("short_interest", sa.BigInteger, nullable=False),
        sa.Column("avg_daily_volume", sa.BigInteger, nullable=True),
        sa.Column("days_to_cover", sa.Double, nullable=True),
        sa.Column("short_pct_float", sa.Double, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_short_interests_symbol_date", "short_interests", ["symbol", "report_date"])

    op.create_table(
        "google_trends",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("keyword", sa.String(128), nullable=False),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("interest", sa.Integer, nullable=False),
        sa.Column("geo", sa.String(8), nullable=False, server_default="US"),
        sa.Column("related_queries", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_google_trends_keyword_date", "google_trends", ["keyword", "date"])

    op.create_table(
        "government_contracts",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("contract_id", sa.String(64), nullable=False, unique=True),
        sa.Column("company_name", sa.String(256), nullable=False),
        sa.Column("symbol", sa.String(32), nullable=True),
        sa.Column("agency", sa.String(256), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("amount", sa.Double, nullable=False),
        sa.Column("award_date", sa.Date, nullable=False),
        sa.Column("completion_date", sa.Date, nullable=True),
        sa.Column("contract_type", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_government_contracts_symbol", "government_contracts", ["symbol"])

    op.create_table(
        "patent_filings",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("patent_number", sa.String(32), nullable=True),
        sa.Column("application_number", sa.String(32), nullable=False, unique=True),
        sa.Column("company_name", sa.String(256), nullable=False),
        sa.Column("symbol", sa.String(32), nullable=True),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("abstract", sa.Text, nullable=True),
        sa.Column("filing_date", sa.Date, nullable=False),
        sa.Column("grant_date", sa.Date, nullable=True),
        sa.Column("patent_type", sa.String(32), nullable=True),
        sa.Column("classifications", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_patent_filings_symbol", "patent_filings", ["symbol"])

    op.create_table(
        "job_postings",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("company_name", sa.String(256), nullable=False),
        sa.Column("symbol", sa.String(32), nullable=True),
        sa.Column("title", sa.String(256), nullable=False),
        sa.Column("department", sa.String(128), nullable=True),
        sa.Column("location", sa.String(256), nullable=True),
        sa.Column("seniority", sa.String(32), nullable=True),
        sa.Column("posted_date", sa.Date, nullable=True),
        sa.Column("url", sa.Text, nullable=True),
        sa.Column("source", sa.String(64), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_job_postings_symbol", "job_postings", ["symbol"])

    op.create_table(
        "weather_impacts",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("severity", sa.String(16), nullable=False),
        sa.Column("region", sa.String(128), nullable=False),
        sa.Column("start_date", sa.Date, nullable=False),
        sa.Column("end_date", sa.Date, nullable=True),
        sa.Column("affected_sectors", JSONB, nullable=True),
        sa.Column("affected_symbols", JSONB, nullable=True),
        sa.Column("estimated_impact", sa.Double, nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("source", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_weather_impacts_date", "weather_impacts", ["start_date"])

    # ══════════════════════════════════════════════════════════════════
    # Knowledge Graph
    # ══════════════════════════════════════════════════════════════════
    op.create_table(
        "kg_entities",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("entity_type", sa.String(32), nullable=False),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("symbol", sa.String(32), nullable=True),
        sa.Column("properties", JSONB, nullable=True),
        sa.Column("external_ids", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_kg_entities_type_name", "kg_entities", ["entity_type", "name"])

    op.create_table(
        "kg_relationships",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("source_id", sa.Integer, sa.ForeignKey("kg_entities.id", ondelete="CASCADE"), nullable=False),
        sa.Column("target_id", sa.Integer, sa.ForeignKey("kg_entities.id", ondelete="CASCADE"), nullable=False),
        sa.Column("relationship_type", sa.String(64), nullable=False),
        sa.Column("weight", sa.Double, nullable=True, server_default="1.0"),
        sa.Column("properties", JSONB, nullable=True),
        sa.Column("valid_from", sa.Date, nullable=True),
        sa.Column("valid_to", sa.Date, nullable=True),
        sa.Column("source", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_kg_relationships_source_target", "kg_relationships", ["source_id", "target_id"])
    op.create_index("ix_kg_relationships_type", "kg_relationships", ["relationship_type"])

    op.create_table(
        "ownership_chains",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("parent_entity_id", sa.Integer, sa.ForeignKey("kg_entities.id", ondelete="CASCADE"), nullable=False),
        sa.Column("child_entity_id", sa.Integer, sa.ForeignKey("kg_entities.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ownership_pct", sa.Double, nullable=True),
        sa.Column("ownership_type", sa.String(32), nullable=True),
        sa.Column("effective_date", sa.Date, nullable=True),
        sa.Column("filing_source", sa.String(128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_ownership_chains_parent", "ownership_chains", ["parent_entity_id"])

    op.create_table(
        "board_interlocks",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("person_entity_id", sa.Integer, sa.ForeignKey("kg_entities.id", ondelete="CASCADE"), nullable=False),
        sa.Column("company_entity_id", sa.Integer, sa.ForeignKey("kg_entities.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(128), nullable=False),
        sa.Column("start_date", sa.Date, nullable=True),
        sa.Column("end_date", sa.Date, nullable=True),
        sa.Column("is_independent", sa.Boolean, nullable=True),
        sa.Column("compensation", sa.Double, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_board_interlocks_person", "board_interlocks", ["person_entity_id"])
    op.create_index("ix_board_interlocks_company", "board_interlocks", ["company_entity_id"])

    # ══════════════════════════════════════════════════════════════════
    # Agent System
    # ══════════════════════════════════════════════════════════════════
    op.create_table(
        "agent_configs",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(128), nullable=False, unique=True),
        sa.Column("agent_type", sa.String(32), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("llm_model", sa.String(64), nullable=True),
        sa.Column("system_prompt", sa.Text, nullable=True),
        sa.Column("tools", JSONB, nullable=True),
        sa.Column("parameters", JSONB, nullable=True),
        sa.Column("schedule_cron", sa.String(64), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "agent_runs",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("agent_id", sa.Integer, sa.ForeignKey("agent_configs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("trigger", sa.String(32), nullable=False, server_default="scheduled"),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("input_data", JSONB, nullable=True),
        sa.Column("output_data", JSONB, nullable=True),
        sa.Column("tokens_used", sa.Integer, nullable=True),
        sa.Column("cost_usd", sa.Double, nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_agent_runs_agent_status", "agent_runs", ["agent_id", "status"])

    op.create_table(
        "agent_findings",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.Integer, sa.ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("finding_type", sa.String(32), nullable=False),
        sa.Column("severity", sa.String(16), nullable=False, server_default="info"),
        sa.Column("title", sa.String(256), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("symbols", JSONB, nullable=True),
        sa.Column("evidence", JSONB, nullable=True),
        sa.Column("confidence", sa.Double, nullable=True),
        sa.Column("actionable", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("acknowledged", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_agent_findings_run", "agent_findings", ["run_id"])
    op.create_index("ix_agent_findings_severity", "agent_findings", ["severity"])

    op.create_table(
        "escalation_rules",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("agent_id", sa.Integer, sa.ForeignKey("agent_configs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("condition", JSONB, nullable=False),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("target_channel", sa.String(128), nullable=True),
        sa.Column("cooldown_minutes", sa.Integer, nullable=False, server_default="60"),
        sa.Column("last_triggered", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # ══════════════════════════════════════════════════════════════════
    # Data Warehouse / Lineage
    # ══════════════════════════════════════════════════════════════════
    op.create_table(
        "dim_assets",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("symbol", sa.String(32), nullable=False, unique=True),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("asset_class", sa.String(32), nullable=False),
        sa.Column("sector", sa.String(64), nullable=True),
        sa.Column("industry", sa.String(128), nullable=True),
        sa.Column("country", sa.String(64), nullable=True),
        sa.Column("exchange", sa.String(32), nullable=True),
        sa.Column("currency", sa.String(8), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("metadata", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "dim_times",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("date", sa.Date, nullable=False, unique=True),
        sa.Column("year", sa.SmallInteger, nullable=False),
        sa.Column("quarter", sa.SmallInteger, nullable=False),
        sa.Column("month", sa.SmallInteger, nullable=False),
        sa.Column("week", sa.SmallInteger, nullable=False),
        sa.Column("day_of_week", sa.SmallInteger, nullable=False),
        sa.Column("is_business_day", sa.Boolean, nullable=False),
        sa.Column("is_us_market_open", sa.Boolean, nullable=False),
        sa.Column("fiscal_quarter", sa.String(8), nullable=True),
    )

    op.create_table(
        "dim_sources",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(64), nullable=False, unique=True),
        sa.Column("source_type", sa.String(32), nullable=False),
        sa.Column("url", sa.Text, nullable=True),
        sa.Column("reliability_score", sa.Double, nullable=True),
        sa.Column("update_frequency", sa.String(32), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "fact_prices",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("asset_id", sa.Integer, sa.ForeignKey("dim_assets.id"), nullable=False),
        sa.Column("time_id", sa.Integer, sa.ForeignKey("dim_times.id"), nullable=False),
        sa.Column("source_id", sa.Integer, sa.ForeignKey("dim_sources.id"), nullable=False),
        sa.Column("open", sa.Double, nullable=True),
        sa.Column("high", sa.Double, nullable=True),
        sa.Column("low", sa.Double, nullable=True),
        sa.Column("close", sa.Double, nullable=False),
        sa.Column("volume", sa.Double, nullable=True),
        sa.Column("vwap", sa.Double, nullable=True),
        sa.Column("market_cap", sa.Double, nullable=True),
        sa.Column("adj_close", sa.Double, nullable=True),
    )
    op.create_index("ix_fact_prices_asset_time", "fact_prices", ["asset_id", "time_id"])

    op.create_table(
        "data_lineage",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("source_table", sa.String(128), nullable=False),
        sa.Column("target_table", sa.String(128), nullable=False),
        sa.Column("transformation", sa.String(256), nullable=True),
        sa.Column("job_name", sa.String(128), nullable=True),
        sa.Column("row_count", sa.BigInteger, nullable=True),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("duration_seconds", sa.Double, nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="success"),
        sa.Column("error_message", sa.Text, nullable=True),
    )
    op.create_index("ix_data_lineage_target", "data_lineage", ["target_table"])

    op.create_table(
        "etl_health",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("pipeline_name", sa.String(128), nullable=False),
        sa.Column("check_time", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("rows_processed", sa.BigInteger, nullable=True),
        sa.Column("rows_failed", sa.BigInteger, nullable=True),
        sa.Column("latency_seconds", sa.Double, nullable=True),
        sa.Column("details", JSONB, nullable=True),
    )
    op.create_index("ix_etl_health_pipeline", "etl_health", ["pipeline_name", "check_time"])

    op.create_table(
        "data_quality_scores",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("table_name", sa.String(128), nullable=False),
        sa.Column("check_date", sa.Date, nullable=False),
        sa.Column("completeness", sa.Double, nullable=True),
        sa.Column("accuracy", sa.Double, nullable=True),
        sa.Column("freshness", sa.Double, nullable=True),
        sa.Column("consistency", sa.Double, nullable=True),
        sa.Column("overall_score", sa.Double, nullable=True),
        sa.Column("issues", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_data_quality_scores_table", "data_quality_scores", ["table_name", "check_date"])

    # ══════════════════════════════════════════════════════════════════
    # Notifications
    # ══════════════════════════════════════════════════════════════════
    op.create_table(
        "notification_channels",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(128), nullable=False, unique=True),
        sa.Column("channel_type", sa.String(32), nullable=False),
        sa.Column("config", JSONB, nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "notification_templates",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(128), nullable=False, unique=True),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("subject_template", sa.Text, nullable=True),
        sa.Column("body_template", sa.Text, nullable=False),
        sa.Column("channel_id", sa.Integer, sa.ForeignKey("notification_channels.id", ondelete="SET NULL"), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "notification_deliveries",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("template_id", sa.Integer, sa.ForeignKey("notification_templates.id", ondelete="SET NULL"), nullable=True),
        sa.Column("channel_id", sa.Integer, sa.ForeignKey("notification_channels.id", ondelete="SET NULL"), nullable=True),
        sa.Column("recipient", sa.String(256), nullable=False),
        sa.Column("subject", sa.Text, nullable=True),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("retry_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_notification_deliveries_status", "notification_deliveries", ["status"])

    op.create_table(
        "digest_configs",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.String(128), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("frequency", sa.String(16), nullable=False, server_default="daily"),
        sa.Column("channel_id", sa.Integer, sa.ForeignKey("notification_channels.id", ondelete="SET NULL"), nullable=True),
        sa.Column("filters", JSONB, nullable=True),
        sa.Column("last_sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "scheduled_reports",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("report_type", sa.String(32), nullable=False),
        sa.Column("schedule_cron", sa.String(64), nullable=False),
        sa.Column("parameters", JSONB, nullable=True),
        sa.Column("recipients", JSONB, nullable=False),
        sa.Column("format", sa.String(16), nullable=False, server_default="pdf"),
        sa.Column("last_generated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # ══════════════════════════════════════════════════════════════════
    # User Analytics / Collaboration
    # ══════════════════════════════════════════════════════════════════
    op.create_table(
        "usage_events",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.String(128), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("event_data", JSONB, nullable=True),
        sa.Column("page", sa.String(256), nullable=True),
        sa.Column("session_id", sa.String(64), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_usage_events_user_time", "usage_events", ["user_id", "created_at"])
    op.create_index("ix_usage_events_type", "usage_events", ["event_type"])

    op.create_table(
        "recommendations",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.String(128), nullable=False),
        sa.Column("recommendation_type", sa.String(32), nullable=False),
        sa.Column("title", sa.String(256), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("target_url", sa.Text, nullable=True),
        sa.Column("relevance_score", sa.Double, nullable=True),
        sa.Column("is_dismissed", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("clicked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_recommendations_user", "recommendations", ["user_id"])

    op.create_table(
        "dashboard_templates",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("layout", JSONB, nullable=False),
        sa.Column("panels", JSONB, nullable=False),
        sa.Column("category", sa.String(64), nullable=True),
        sa.Column("is_public", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("author_id", sa.String(128), nullable=True),
        sa.Column("usage_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "saved_research",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.String(128), nullable=False),
        sa.Column("title", sa.String(256), nullable=False),
        sa.Column("research_type", sa.String(32), nullable=False),
        sa.Column("content", JSONB, nullable=False),
        sa.Column("symbols", JSONB, nullable=True),
        sa.Column("tags", JSONB, nullable=True),
        sa.Column("is_public", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_saved_research_user", "saved_research", ["user_id"])

    op.create_table(
        "teams",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("owner_id", sa.String(128), nullable=False),
        sa.Column("settings", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "team_members",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("team_id", sa.Integer, sa.ForeignKey("teams.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.String(128), nullable=False),
        sa.Column("role", sa.String(32), nullable=False, server_default="member"),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_team_members_team_user", "team_members", ["team_id", "user_id"], unique=True)

    op.create_table(
        "shared_workspaces",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("team_id", sa.Integer, sa.ForeignKey("teams.id", ondelete="CASCADE"), nullable=False),
        sa.Column("workspace_type", sa.String(32), nullable=False, server_default="analysis"),
        sa.Column("config", JSONB, nullable=False, server_default="{}"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_shared_workspaces_team", "shared_workspaces", ["team_id"])

    # ══════════════════════════════════════════════════════════════════
    # Compliance & Governance
    # ══════════════════════════════════════════════════════════════════
    op.create_table(
        "compliance_audit_logs",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.String(128), nullable=True),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("resource_type", sa.String(64), nullable=False),
        sa.Column("resource_id", sa.String(128), nullable=True),
        sa.Column("details", JSONB, nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.Text, nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="success"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_compliance_audit_user", "compliance_audit_logs", ["user_id", "created_at"])
    op.create_index("ix_compliance_audit_action", "compliance_audit_logs", ["action"])

    op.create_table(
        "data_retention_policies",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("table_name", sa.String(128), nullable=False, unique=True),
        sa.Column("retention_days", sa.Integer, nullable=False),
        sa.Column("archive_before_delete", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("archive_location", sa.Text, nullable=True),
        sa.Column("last_enforced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "access_policies",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(128), nullable=False, unique=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("resource_pattern", sa.String(256), nullable=False),
        sa.Column("allowed_roles", JSONB, nullable=False),
        sa.Column("conditions", JSONB, nullable=True),
        sa.Column("effect", sa.String(8), nullable=False, server_default="allow"),
        sa.Column("priority", sa.Integer, nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "export_rate_limits",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.String(128), nullable=False),
        sa.Column("export_type", sa.String(32), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("request_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("bytes_exported", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column("max_requests", sa.Integer, nullable=False, server_default="100"),
        sa.Column("max_bytes", sa.BigInteger, nullable=False, server_default="1073741824"),
    )
    op.create_index("ix_export_rate_limits_user", "export_rate_limits", ["user_id", "export_type", "window_start"])

    op.create_table(
        "api_usage_meters",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.String(128), nullable=False),
        sa.Column("endpoint", sa.String(256), nullable=False),
        sa.Column("method", sa.String(8), nullable=False),
        sa.Column("status_code", sa.SmallInteger, nullable=False),
        sa.Column("response_time_ms", sa.Double, nullable=True),
        sa.Column("request_size", sa.Integer, nullable=True),
        sa.Column("response_size", sa.Integer, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_api_usage_meters_user", "api_usage_meters", ["user_id", "created_at"])
    op.create_index("ix_api_usage_meters_endpoint", "api_usage_meters", ["endpoint"])


def downgrade() -> None:
    # Compliance & Governance
    op.drop_table("api_usage_meters")
    op.drop_table("export_rate_limits")
    op.drop_table("access_policies")
    op.drop_table("data_retention_policies")
    op.drop_table("compliance_audit_logs")

    # User Analytics / Collaboration
    op.drop_table("shared_workspaces")
    op.drop_table("team_members")
    op.drop_table("teams")
    op.drop_table("saved_research")
    op.drop_table("dashboard_templates")
    op.drop_table("recommendations")
    op.drop_table("usage_events")

    # Notifications
    op.drop_table("scheduled_reports")
    op.drop_table("digest_configs")
    op.drop_table("notification_deliveries")
    op.drop_table("notification_templates")
    op.drop_table("notification_channels")

    # Data Warehouse / Lineage
    op.drop_table("data_quality_scores")
    op.drop_table("etl_health")
    op.drop_table("data_lineage")
    op.drop_table("fact_prices")
    op.drop_table("dim_sources")
    op.drop_table("dim_times")
    op.drop_table("dim_assets")

    # Agent System
    op.drop_table("escalation_rules")
    op.drop_table("agent_findings")
    op.drop_table("agent_runs")
    op.drop_table("agent_configs")

    # Knowledge Graph
    op.drop_table("board_interlocks")
    op.drop_table("ownership_chains")
    op.drop_table("kg_relationships")
    op.drop_table("kg_entities")

    # Alternative Data
    op.drop_table("weather_impacts")
    op.drop_table("job_postings")
    op.drop_table("patent_filings")
    op.drop_table("government_contracts")
    op.drop_table("google_trends")
    op.drop_table("short_interests")
    op.drop_table("insider_trades")

    # NLP / Market Briefings
    op.drop_table("market_briefings")
    op.drop_table("nlp_documents")

    # Backtesting
    op.drop_table("backtest_trades")
    op.drop_table("backtest_runs")
    op.drop_table("strategies")

    # Quant Analytics
    op.drop_table("covariance_matrices")
    op.drop_table("var_results")
    op.drop_table("option_chains")
    op.drop_table("yield_curves")

    # RBAC
    op.drop_table("roles")
