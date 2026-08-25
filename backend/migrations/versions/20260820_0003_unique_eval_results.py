"""Enforce one result per evaluator and run item.

Revision ID: 20260820_0003
Revises: 20260820_0002
Create Date: 2026-08-20
"""

from __future__ import annotations

from alembic import op

revision = "20260820_0003"
down_revision = "20260820_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "DELETE FROM eval_results WHERE id IN ("
        "SELECT id FROM ("
        "SELECT id, row_number() OVER ("
        "PARTITION BY run_item_id, evaluator_name "
        "ORDER BY created_at DESC, id DESC"
        ") AS duplicate_rank FROM eval_results"
        ") ranked WHERE duplicate_rank > 1"
        ")"
    )
    op.drop_index(
        "ix_eval_results_run_item_id_evaluator_name",
        table_name="eval_results",
    )
    op.create_unique_constraint(
        "uq_eval_results_run_item_id_evaluator_name",
        "eval_results",
        ["run_item_id", "evaluator_name"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_eval_results_run_item_id_evaluator_name",
        "eval_results",
        type_="unique",
    )
    op.create_index(
        "ix_eval_results_run_item_id_evaluator_name",
        "eval_results",
        ["run_item_id", "evaluator_name"],
    )
