"""Additive IAM registry and immutable case-assignment history.

Revision ID: 003_iam_officers
Revises: 002_create_rag_tables
This migration never replaces existing case/evidence/RAG tables or records.
"""
from alembic import op
import sqlalchemy as sa

revision = "003_iam_officers"
down_revision = "002_create_rag_tables"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind(); inspector = sa.inspect(bind); present = set(inspector.get_table_names())
    if "organizations" not in present:
        op.create_table("organizations", sa.Column("id", sa.String(36), primary_key=True), sa.Column("organization_id", sa.String(64), nullable=False, unique=True), sa.Column("name", sa.String(255), nullable=False), sa.Column("code", sa.String(64), nullable=False, unique=True), sa.Column("status", sa.String(32), nullable=False), sa.Column("created_by", sa.String(128), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))
    if "jurisdictions" not in present:
        op.create_table("jurisdictions", sa.Column("id", sa.String(36), primary_key=True), sa.Column("jurisdiction_id", sa.String(64), nullable=False, unique=True), sa.Column("organization_id", sa.String(64), sa.ForeignKey("organizations.organization_id"), nullable=False), sa.Column("name", sa.String(255), nullable=False), sa.Column("code", sa.String(64), nullable=False, unique=True), sa.Column("status", sa.String(32), nullable=False), sa.Column("created_by", sa.String(128), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))
    if "police_stations" not in present:
        op.create_table("police_stations", sa.Column("id", sa.String(36), primary_key=True), sa.Column("station_id", sa.String(64), nullable=False, unique=True), sa.Column("organization_id", sa.String(64), sa.ForeignKey("organizations.organization_id"), nullable=False), sa.Column("jurisdiction_id", sa.String(64), sa.ForeignKey("jurisdictions.jurisdiction_id"), nullable=False), sa.Column("name", sa.String(255), nullable=False), sa.Column("code", sa.String(64), nullable=False, unique=True), sa.Column("status", sa.String(32), nullable=False), sa.Column("created_by", sa.String(128), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))
    if "officers" not in present:
        op.create_table("officers", sa.Column("id", sa.String(36), primary_key=True), sa.Column("officer_id", sa.String(64), nullable=False, unique=True), sa.Column("firebase_uid", sa.String(128), unique=True), sa.Column("firebase_login_identifier", sa.String(255), unique=True), sa.Column("full_name", sa.String(255), nullable=False), sa.Column("mobile_e164", sa.String(16), nullable=False, unique=True), sa.Column("username", sa.String(80), nullable=False, unique=True), sa.Column("service_identifier", sa.String(128), unique=True), sa.Column("role", sa.String(64), nullable=False), sa.Column("organization_id", sa.String(64), sa.ForeignKey("organizations.organization_id"), nullable=False), sa.Column("station_id", sa.String(64), sa.ForeignKey("police_stations.station_id"), nullable=False), sa.Column("jurisdiction_id", sa.String(64), sa.ForeignKey("jurisdictions.jurisdiction_id"), nullable=False), sa.Column("status", sa.String(32), nullable=False), sa.Column("mobile_verified", sa.Boolean(), nullable=False), sa.Column("created_by", sa.String(128), nullable=False), sa.Column("updated_by", sa.String(128), nullable=False), sa.Column("deactivated_by", sa.String(128)), sa.Column("deactivated_at", sa.DateTime(timezone=True)), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))
    if "case_assignments" not in present:
        op.create_table("case_assignments", sa.Column("id", sa.String(36), primary_key=True), sa.Column("assignment_id", sa.String(64), nullable=False, unique=True), sa.Column("case_id", sa.String(64), sa.ForeignKey("cases.case_id"), nullable=False), sa.Column("officer_id", sa.String(64), sa.ForeignKey("officers.officer_id"), nullable=False), sa.Column("previous_officer_id", sa.String(64)), sa.Column("assigned_by", sa.String(128), nullable=False), sa.Column("reason", sa.Text(), nullable=False), sa.Column("status", sa.String(32), nullable=False), sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=False), sa.Column("ended_at", sa.DateTime(timezone=True)))
    if "id_sequences" not in present:
        op.create_table("id_sequences", sa.Column("name", sa.String(64), primary_key=True), sa.Column("current_value", sa.Integer(), nullable=False, default=0))


def downgrade():
    # Only tables introduced by this revision are removed; no authoritative evidence/case data is touched.
    for name in ("id_sequences", "case_assignments", "officers", "police_stations", "jurisdictions", "organizations"):
        if name in sa.inspect(op.get_bind()).get_table_names(): op.drop_table(name)
