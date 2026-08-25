"""Add worker delivery leases for idempotent task execution.

Revision ID: 20260820_0002
Revises: 20260605_0001
Create Date: 2026-08-20
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260820_0002"
down_revision = "20260605_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "eval_run_items",
        sa.Column("worker_task_id", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "eval_run_items",
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("eval_run_items", "lease_expires_at")
    op.drop_column("eval_run_items", "worker_task_id")
