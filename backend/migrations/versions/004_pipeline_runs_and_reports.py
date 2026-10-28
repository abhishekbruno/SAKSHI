"""End-to-End Automated Investigation Pipeline runs and case reports schema.

Revision ID: 004_pipeline_runs_and_reports
Revises: 003_iam_officers
Create Date: 2026-10-28 19:55:00 UTC
"""
from alembic import op
import sqlalchemy as sa

revision = "004_pipeline_runs_and_reports"
down_revision = "003_iam_officers"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    present = set(inspector.get_table_names())

    if "pipeline_runs" not in present:
        op.create_table(
            "pipeline_runs",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("run_id", sa.String(64), nullable=False, unique=True),
            sa.Column("case_id", sa.String(64), sa.ForeignKey("cases.case_id"), nullable=False),
            sa.Column("status", sa.String(32), nullable=False, server_default="PENDING"),
            sa.Column("requested_by", sa.String(128), nullable=False),
            sa.Column("current_stage", sa.String(64), nullable=False, server_default="CASE_INTAKE"),
            sa.Column("stage_summary", sa.JSON, nullable=True),
            sa.Column("error_summary", sa.Text, nullable=True),
            sa.Column("retry_metadata", sa.JSON, nullable=True),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_pipeline_runs_id", "pipeline_runs", ["id"])
        op.create_index("ix_pipeline_runs_run_id", "pipeline_runs", ["run_id"], unique=True)
        op.create_index("ix_pipeline_runs_case_id", "pipeline_runs", ["case_id"])
        op.create_index("ix_pipeline_runs_status", "pipeline_runs", ["status"])
        op.create_index("ix_pipeline_runs_requested_by", "pipeline_runs", ["requested_by"])
        op.create_index("ix_pipeline_runs_case_status", "pipeline_runs", ["case_id", "status"])

    if "pipeline_stage_runs" not in present:
        op.create_table(
            "pipeline_stage_runs",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("stage_run_id", sa.String(64), nullable=False, unique=True),
            sa.Column("run_id", sa.String(64), sa.ForeignKey("pipeline_runs.run_id"), nullable=False),
            sa.Column("case_id", sa.String(64), sa.ForeignKey("cases.case_id"), nullable=False),
            sa.Column("stage_name", sa.String(64), nullable=False),
            sa.Column("status", sa.String(32), nullable=False, server_default="PENDING"),
            sa.Column("input_ref", sa.JSON, nullable=True),
            sa.Column("output_ref", sa.JSON, nullable=True),
            sa.Column("attempt_count", sa.Integer, nullable=False, server_default="1"),
            sa.Column("error_code", sa.String(64), nullable=True),
            sa.Column("error_details", sa.JSON, nullable=True),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index("ix_pipeline_stage_runs_id", "pipeline_stage_runs", ["id"])
        op.create_index("ix_pipeline_stage_runs_stage_run_id", "pipeline_stage_runs", ["stage_run_id"], unique=True)
        op.create_index("ix_pipeline_stage_runs_run_id", "pipeline_stage_runs", ["run_id"])
        op.create_index("ix_pipeline_stage_runs_case_id", "pipeline_stage_runs", ["case_id"])
        op.create_index("ix_pipeline_stage_runs_stage_name", "pipeline_stage_runs", ["stage_name"])
        op.create_index("ix_pipeline_stage_runs_status", "pipeline_stage_runs", ["status"])
        op.create_index("ix_stage_runs_run_stage", "pipeline_stage_runs", ["run_id", "stage_name"])

    if "case_reports" not in present:
        op.create_table(
            "case_reports",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("report_id", sa.String(64), nullable=False, unique=True),
            sa.Column("case_id", sa.String(64), sa.ForeignKey("cases.case_id"), nullable=False),
            sa.Column("pipeline_run_id", sa.String(64), nullable=True),
            sa.Column("version", sa.String(32), nullable=False, server_default="v1.0"),
            sa.Column("status", sa.String(32), nullable=False, server_default="PRELIMINARY"),
            sa.Column("title", sa.String(255), nullable=False),
            sa.Column("incident_type", sa.String(64), nullable=False, server_default="NEEDS_REVIEW"),
            sa.Column("executive_summary", sa.Text, nullable=True),
            sa.Column("content", sa.JSON, nullable=False),
            sa.Column("citation_mappings", sa.JSON, nullable=True),
            sa.Column("limitations", sa.JSON, nullable=True),
            sa.Column("unresolved_questions", sa.JSON, nullable=True),
            sa.Column("approval_status", sa.String(32), nullable=False, server_default="PENDING_REVIEW"),
            sa.Column("approved_by", sa.String(128), nullable=True),
            sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("review_notes", sa.Text, nullable=True),
            sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_case_reports_id", "case_reports", ["id"])
        op.create_index("ix_case_reports_report_id", "case_reports", ["report_id"], unique=True)
        op.create_index("ix_case_reports_case_id", "case_reports", ["case_id"])
        op.create_index("ix_case_reports_pipeline_run_id", "case_reports", ["pipeline_run_id"])
        op.create_index("ix_case_reports_status", "case_reports", ["status"])
        op.create_index("ix_case_reports_case_version", "case_reports", ["case_id", "version"])


def downgrade():
    for name in ("case_reports", "pipeline_stage_runs", "pipeline_runs"):
        if name in sa.inspect(op.get_bind()).get_table_names():
            op.drop_table(name)
