"""Baseline schema for SAKSHI Investigation Platform.

Registers authoritative Case and Evidence tables (MOD-01 through MOD-11).
Designed to be non-destructive: inspects existing tables so databases with existing
records (e.g. active sakshi_cases.db) establish a baseline without data loss.

Revision ID: 001_baseline
Revises: 
Create Date: 2026-10-13 14:45:00 UTC

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "001_baseline"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    try:
        inspector = sa.inspect(bind)
        existing_tables = inspector.get_table_names()
    except Exception:
        existing_tables = []

    # 1. Create cases table if not already present
    if "cases" not in existing_tables:
        op.create_table(
            "cases",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("case_id", sa.String(length=64), unique=True, nullable=False),
            sa.Column("title", sa.String(length=255), nullable=False),
            sa.Column("fir_metadata", sa.JSON(), nullable=False),
            sa.Column("assigned_io_id", sa.String(length=128), nullable=False),
            sa.Column("lifecycle_stage", sa.String(length=64), nullable=False, server_default="INITIALIZED"),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="ACTIVE"),
            sa.Column("case_workspace_path", sa.String(length=512), nullable=False),
            sa.Column("created_by", sa.String(length=128), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_cases_id", "cases", ["id"])
        op.create_index("ix_cases_case_id", "cases", ["case_id"], unique=True)
        op.create_index("ix_cases_assigned_io_id", "cases", ["assigned_io_id"])
        op.create_index("ix_cases_lifecycle_stage", "cases", ["lifecycle_stage"])

    # 2. Create evidence table if not already present
    if "evidence" not in existing_tables:
        op.create_table(
            "evidence",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("evidence_id", sa.String(length=64), unique=True, nullable=False),
            sa.Column("case_id", sa.String(length=64), sa.ForeignKey("cases.case_id"), nullable=False),
            sa.Column("original_file_name", sa.String(length=255), nullable=False),
            sa.Column("stored_file_name", sa.String(length=255), nullable=False),
            sa.Column("evidence_category", sa.String(length=64), nullable=False),
            sa.Column("declared_mime_type", sa.String(length=128), nullable=False),
            sa.Column("file_size_bytes", sa.Integer(), nullable=False),
            sa.Column("collection_datetime", sa.DateTime(timezone=True), nullable=True),
            sa.Column("collection_location", sa.String(length=255), nullable=True),
            sa.Column("source_device_or_person", sa.String(length=255), nullable=True),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("submitting_investigator_id", sa.String(length=128), nullable=False),
            sa.Column("status", sa.String(length=64), nullable=False, server_default="REGISTERED_INTAKE"),
            # MOD-06 MIME
            sa.Column("detected_mime_type", sa.String(length=128), nullable=True),
            sa.Column("detected_format", sa.String(length=64), nullable=True),
            sa.Column("validation_reason", sa.Text(), nullable=True),
            sa.Column("validated_at", sa.DateTime(timezone=True), nullable=True),
            # MOD-07 Antivirus
            sa.Column("antivirus_status", sa.String(length=64), nullable=True),
            sa.Column("antivirus_scanner", sa.String(length=64), nullable=True),
            sa.Column("antivirus_version", sa.String(length=64), nullable=True),
            sa.Column("antivirus_threat_name", sa.String(length=255), nullable=True),
            sa.Column("antivirus_message", sa.Text(), nullable=True),
            sa.Column("antivirus_scanned_at", sa.DateTime(timezone=True), nullable=True),
            # MOD-08 WORM
            sa.Column("checksum_algorithm", sa.String(length=32), nullable=True),
            sa.Column("checksum_sha256", sa.String(length=64), nullable=True),
            sa.Column("checksum_computed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("worm_status", sa.String(length=64), nullable=True),
            sa.Column("worm_storage_reference", sa.String(length=512), nullable=True),
            sa.Column("worm_committed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("worm_commit_message", sa.Text(), nullable=True),
            # MOD-09 Dual Hashing
            sa.Column("checksum_sha3_512", sa.String(length=128), nullable=True),
            sa.Column("sha3_512_computed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("integrity_status", sa.String(length=32), nullable=True, server_default="UNVERIFIED"),
            sa.Column("integrity_verified_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("integrity_verification_message", sa.Text(), nullable=True),
            # MOD-10 Object Lock
            sa.Column("lock_status", sa.String(length=32), nullable=True, server_default="UNLOCKED"),
            sa.Column("lock_mode", sa.String(length=32), nullable=True),
            sa.Column("lock_storage_reference", sa.String(length=512), nullable=True),
            sa.Column("lock_applied_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("lock_retention_until", sa.DateTime(timezone=True), nullable=True),
            sa.Column("lock_backend", sa.String(length=64), nullable=True),
            sa.Column("lock_overwrite_protected", sa.Boolean(), nullable=True, server_default=sa.text("0")),
            sa.Column("lock_delete_protected", sa.Boolean(), nullable=True, server_default=sa.text("0")),
            sa.Column("lock_integrity_binding", sa.String(length=256), nullable=True),
            sa.Column("lock_failure_reason", sa.Text(), nullable=True),
            sa.Column("object_lock_event_log", sa.Text(), nullable=True),
            # MOD-11 AES-256-GCM
            sa.Column("encryption_status", sa.String(length=32), nullable=True, server_default="UNENCRYPTED"),
            sa.Column("encryption_algorithm", sa.String(length=32), nullable=True),
            sa.Column("encryption_key_reference", sa.String(length=256), nullable=True),
            sa.Column("encryption_key_provider", sa.String(length=64), nullable=True),
            sa.Column("encryption_storage_reference", sa.String(length=512), nullable=True),
            sa.Column("encryption_nonce_hex", sa.String(length=64), nullable=True),
            sa.Column("encryption_auth_tag_hex", sa.String(length=64), nullable=True),
            sa.Column("encryption_aad", sa.Text(), nullable=True),
            sa.Column("ciphertext_sha256", sa.String(length=64), nullable=True),
            sa.Column("encrypted_file_size_bytes", sa.Integer(), nullable=True),
            sa.Column("encrypted_file_path", sa.String(length=512), nullable=True),
            sa.Column("encrypted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("encryption_failure_reason", sa.Text(), nullable=True),
            sa.Column("encryption_event_log", sa.Text(), nullable=True),
            sa.Column("raw_storage_path", sa.String(length=512), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_evidence_id", "evidence", ["id"])
        op.create_index("ix_evidence_evidence_id", "evidence", ["evidence_id"], unique=True)
        op.create_index("ix_evidence_case_id", "evidence", ["case_id"])
        op.create_index("ix_evidence_evidence_category", "evidence", ["evidence_category"])
        op.create_index("ix_evidence_submitting_investigator_id", "evidence", ["submitting_investigator_id"])
        op.create_index("ix_evidence_status", "evidence", ["status"])
        op.create_index("ix_evidence_checksum_sha256", "evidence", ["checksum_sha256"])
        op.create_index("ix_evidence_checksum_sha3_512", "evidence", ["checksum_sha3_512"])
        op.create_index("ix_evidence_lock_status", "evidence", ["lock_status"])
        op.create_index("ix_evidence_encryption_status", "evidence", ["encryption_status"])
        op.create_index("ix_evidence_ciphertext_sha256", "evidence", ["ciphertext_sha256"])


def downgrade() -> None:
    # Baseline tables are preserved during downgrade to prevent accidental evidence destruction
    pass
