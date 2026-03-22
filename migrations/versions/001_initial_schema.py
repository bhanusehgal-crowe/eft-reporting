"""Initial schema — all Phase 1 + Phase 2 tables.

Revision ID: 001
Revises:
Create Date: 2026-03-22
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "reconciliation_runs",
        sa.Column("run_id", sa.String(36), primary_key=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="PENDING"),
        sa.Column("triggered_by", sa.String(255), nullable=False),
        sa.Column("operator_id", sa.String(255), nullable=False),
        sa.Column("started_at", sa.DateTime, nullable=True),
        sa.Column("completed_at", sa.DateTime, nullable=True),
        sa.Column("parameters", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )

    op.create_table(
        "eft_transactions",
        sa.Column("transaction_id", sa.String(255), primary_key=True),
        sa.Column("run_id", sa.String(36), sa.ForeignKey("reconciliation_runs.run_id"), nullable=False),
        sa.Column("source_file", sa.String(500), nullable=False),
        sa.Column("row_hash", sa.String(64), nullable=False, index=True),
        sa.Column("value_date", sa.Date, nullable=False),
        sa.Column("settlement_date", sa.Date, nullable=True),
        sa.Column("amount", sa.Numeric(18, 4), nullable=False),
        sa.Column("currency_code", sa.String(3), nullable=False),
        sa.Column("cad_amount", sa.Numeric(18, 4), nullable=False),
        sa.Column("cad_conversion_rate", sa.Numeric(18, 6), nullable=True),
        sa.Column("direction", sa.String(20), nullable=False, index=True),
        sa.Column("originator_name", sa.Text, nullable=False),
        sa.Column("originator_address", sa.Text, nullable=True),
        sa.Column("originator_account", sa.String(255), nullable=True),
        sa.Column("beneficiary_name", sa.Text, nullable=False),
        sa.Column("beneficiary_address", sa.Text, nullable=True),
        sa.Column("beneficiary_account", sa.String(255), nullable=True),
        sa.Column("counterparty_id", sa.String(255), nullable=True),
        sa.Column("transaction_type", sa.String(100), nullable=True),
        sa.Column("raw_payload", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )

    op.create_table(
        "reported_transactions",
        sa.Column("reported_id", sa.String(36), primary_key=True),
        sa.Column("run_id", sa.String(36), sa.ForeignKey("reconciliation_runs.run_id"), nullable=False),
        sa.Column("source_file", sa.String(500), nullable=False),
        sa.Column("row_hash", sa.String(64), nullable=False, index=True),
        sa.Column("report_reference", sa.String(255), nullable=False),
        sa.Column("reporting_entity_id", sa.String(255), nullable=False),
        sa.Column("reported_transaction_id", sa.String(255), nullable=False, index=True),
        sa.Column("report_date", sa.Date, nullable=False),
        sa.Column("reported_amount", sa.Numeric(18, 4), nullable=False),
        sa.Column("reported_currency", sa.String(3), nullable=False),
        sa.Column("reported_cad_amount", sa.Numeric(18, 4), nullable=True),
        sa.Column("report_type", sa.String(100), nullable=False),
        sa.Column("direction", sa.String(20), nullable=False),
        sa.Column("raw_payload", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )

    op.create_table(
        "reconciliation_results",
        sa.Column("result_id", sa.String(36), primary_key=True),
        sa.Column("run_id", sa.String(36), sa.ForeignKey("reconciliation_runs.run_id"), nullable=False),
        sa.Column("eft_transaction_id", sa.String(255), nullable=True, index=True),
        sa.Column("reported_id", sa.String(36), nullable=True, index=True),
        sa.Column("status", sa.String(20), nullable=False, index=True),
        sa.Column("match_method", sa.String(100), nullable=True),
        sa.Column("variance_amount", sa.Numeric(18, 4), nullable=True),
        sa.Column("detail", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )

    op.create_table(
        "rules",
        sa.Column("rule_id", sa.String(36), primary_key=True),
        sa.Column("rule_code", sa.String(100), nullable=False, index=True),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("parent_version_id", sa.String(36), nullable=True),
        sa.Column("rule_name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("rule_type", sa.String(50), nullable=False),
        sa.Column("parameters", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("severity", sa.String(20), nullable=False, index=True),
        sa.Column("effective_from", sa.Date, nullable=False),
        sa.Column("effective_to", sa.Date, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="1"),
        sa.Column("change_reason", sa.Text, nullable=False, server_default=""),
        sa.Column("changed_by", sa.String(255), nullable=False, server_default="system"),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )

    op.create_table(
        "rule_findings",
        sa.Column("finding_id", sa.String(36), primary_key=True),
        sa.Column("run_id", sa.String(36), sa.ForeignKey("reconciliation_runs.run_id"), nullable=False),
        sa.Column("rule_id", sa.String(36), nullable=False),
        sa.Column("rule_code", sa.String(100), nullable=False, index=True),
        sa.Column("rule_version", sa.Integer, nullable=False),
        sa.Column("transaction_id", sa.String(255), nullable=True, index=True),
        sa.Column("severity", sa.String(20), nullable=False, index=True),
        sa.Column("detail", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )

    op.create_table(
        "audit_log",
        sa.Column("log_id", sa.String(36), primary_key=True),
        sa.Column("run_id", sa.String(36), nullable=True, index=True),
        sa.Column("event_type", sa.String(100), nullable=False, index=True),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("component", sa.String(100), nullable=False),
        sa.Column("operator_id", sa.String(255), nullable=True),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("detail", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )

    op.create_table(
        "reperformance_results",
        sa.Column("result_id", sa.String(36), primary_key=True),
        sa.Column("run_id", sa.String(36), sa.ForeignKey("reconciliation_runs.run_id"), nullable=False),
        sa.Column("calculation_type", sa.String(100), nullable=False, index=True),
        sa.Column("period", sa.String(50), nullable=True),
        sa.Column("reported_value", sa.Numeric(18, 4), nullable=True),
        sa.Column("reperformed_value", sa.Numeric(18, 4), nullable=True),
        sa.Column("variance_absolute", sa.Numeric(18, 4), nullable=True),
        sa.Column("variance_pct", sa.Numeric(10, 6), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, index=True),
        sa.Column("threshold_rule_id", sa.String(36), nullable=True),
        sa.Column("detail", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )


def downgrade() -> None:
    op.drop_table("reperformance_results")
    op.drop_table("audit_log")
    op.drop_table("rule_findings")
    op.drop_table("rules")
    op.drop_table("reconciliation_results")
    op.drop_table("reported_transactions")
    op.drop_table("eft_transactions")
    op.drop_table("reconciliation_runs")
