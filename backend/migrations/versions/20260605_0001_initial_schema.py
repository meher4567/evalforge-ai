"""Initial EvalForge schema.

Revision ID: 20260605_0001
Revises:
Create Date: 2026-06-05
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision = "20260605_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "apps",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_apps_name", "apps", ["name"], unique=True)

    op.create_table(
        "eval_cases",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("external_id", sa.String(length=255), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_eval_cases_external_id", "eval_cases", ["external_id"])

    op.create_table(
        "evaluator_configs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("config", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_evaluator_configs_name", "evaluator_configs", ["name"], unique=True)

    op.create_table(
        "gate_rules",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("rules", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_unique_constraint("uq_gate_rules_name", "gate_rules", ["name"])

    op.create_table(
        "embedding_cache",
        sa.Column("text_hash", sa.String(length=64), primary_key=True),
        sa.Column("model_id", sa.String(length=120), primary_key=True),
        sa.Column("embedding", Vector(384), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "app_versions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("app_id", sa.String(length=36), sa.ForeignKey("apps.id", ondelete="CASCADE")),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("config", sa.JSON(), nullable=False),
        sa.Column("adapter_module", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("app_id", "name", name="uq_app_versions_app_id_name"),
    )
    op.create_index("ix_app_versions_app_id", "app_versions", ["app_id"])

    op.create_table(
        "eval_suites",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("app_id", sa.String(length=36), sa.ForeignKey("apps.id", ondelete="CASCADE")),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("app_id", "name", name="uq_eval_suites_app_id_name"),
    )
    op.create_index("ix_eval_suites_app_id", "eval_suites", ["app_id"])

    op.create_table(
        "eval_suite_cases",
        sa.Column(
            "suite_id",
            sa.String(length=36),
            sa.ForeignKey("eval_suites.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "case_id",
            sa.String(length=36),
            sa.ForeignKey("eval_cases.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "eval_runs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("app_version_id", sa.String(length=36), sa.ForeignKey("app_versions.id")),
        sa.Column("suite_id", sa.String(length=36), sa.ForeignKey("eval_suites.id")),
        sa.Column(
            "evaluator_config_id",
            sa.String(length=36),
            sa.ForeignKey("evaluator_configs.id"),
        ),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("case_count", sa.Integer(), nullable=False),
        sa.Column("case_completed", sa.Integer(), nullable=False),
        sa.Column("case_errored", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_eval_runs_app_version_id", "eval_runs", ["app_version_id"])
    op.create_index("ix_eval_runs_evaluator_config_id", "eval_runs", ["evaluator_config_id"])
    op.create_index("ix_eval_runs_status", "eval_runs", ["status"])
    op.create_index("ix_eval_runs_suite_id", "eval_runs", ["suite_id"])

    op.create_table(
        "eval_run_items",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "run_id",
            sa.String(length=36),
            sa.ForeignKey("eval_runs.id", ondelete="CASCADE"),
        ),
        sa.Column("case_id", sa.String(length=36), sa.ForeignKey("eval_cases.id")),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("recorded_latency_ms", sa.Integer(), nullable=True),
        sa.Column("recorded_cost_usd", sa.Numeric(10, 6), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("run_id", "case_id", name="uq_eval_run_items_run_id_case_id"),
    )
    op.create_index("ix_eval_run_items_case_id", "eval_run_items", ["case_id"])
    op.create_index("ix_eval_run_items_run_id", "eval_run_items", ["run_id"])
    op.create_index("ix_eval_run_items_run_id_status", "eval_run_items", ["run_id", "status"])

    op.create_table(
        "traces",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "run_item_id",
            sa.String(length=36),
            sa.ForeignKey("eval_run_items.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_traces_run_item_id", "traces", ["run_item_id"], unique=True)

    op.create_table(
        "eval_results",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "run_item_id",
            sa.String(length=36),
            sa.ForeignKey("eval_run_items.id", ondelete="CASCADE"),
        ),
        sa.Column("evaluator_name", sa.String(length=120), nullable=False),
        sa.Column("score", sa.Numeric(10, 6), nullable=True),
        sa.Column("passed", sa.Boolean(), nullable=True),
        sa.Column("errored", sa.Boolean(), nullable=False),
        sa.Column("skipped", sa.Boolean(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_eval_results_run_item_id", "eval_results", ["run_item_id"])
    op.create_index(
        "ix_eval_results_run_item_id_evaluator_name",
        "eval_results",
        ["run_item_id", "evaluator_name"],
    )

    op.create_table(
        "comparisons",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("baseline_run_id", sa.String(length=36), sa.ForeignKey("eval_runs.id")),
        sa.Column("candidate_run_id", sa.String(length=36), sa.ForeignKey("eval_runs.id")),
        sa.Column("gate_rules_id", sa.String(length=36), sa.ForeignKey("gate_rules.id")),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_comparisons_baseline_run_id", "comparisons", ["baseline_run_id"])
    op.create_index("ix_comparisons_candidate_run_id", "comparisons", ["candidate_run_id"])
    op.create_index("ix_comparisons_gate_rules_id", "comparisons", ["gate_rules_id"])

    op.create_table(
        "regression_reports",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "comparison_id",
            sa.String(length=36),
            sa.ForeignKey("comparisons.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("metrics", sa.JSON(), nullable=False),
        sa.Column("gate_verdict", sa.String(length=20), nullable=False),
        sa.Column("gate_reasons", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("comparison_id", name="uq_regression_reports_comparison_id"),
    )

    op.create_table(
        "gold_labels",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("case_id", sa.String(length=36), sa.ForeignKey("eval_cases.id")),
        sa.Column("version_id", sa.String(length=36), sa.ForeignKey("app_versions.id")),
        sa.Column(
            "run_item_id",
            sa.String(length=36),
            sa.ForeignKey("eval_run_items.id"),
            nullable=True,
        ),
        sa.Column("output_hash", sa.String(length=64), nullable=True),
        sa.Column("label_score", sa.Integer(), nullable=False),
        sa.Column("labeler_id", sa.String(length=120), nullable=False),
        sa.Column("rubric_version", sa.String(length=40), nullable=False),
        sa.Column("labeled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
    )
    op.create_index("ix_gold_labels_case_id", "gold_labels", ["case_id"])
    op.create_index("ix_gold_labels_version_id", "gold_labels", ["version_id"])


def downgrade() -> None:
    op.drop_index("ix_gold_labels_version_id", table_name="gold_labels")
    op.drop_index("ix_gold_labels_case_id", table_name="gold_labels")
    op.drop_table("gold_labels")
    op.drop_table("regression_reports")
    op.drop_index("ix_comparisons_gate_rules_id", table_name="comparisons")
    op.drop_index("ix_comparisons_candidate_run_id", table_name="comparisons")
    op.drop_index("ix_comparisons_baseline_run_id", table_name="comparisons")
    op.drop_table("comparisons")
    op.drop_index("ix_eval_results_run_item_id_evaluator_name", table_name="eval_results")
    op.drop_index("ix_eval_results_run_item_id", table_name="eval_results")
    op.drop_table("eval_results")
    op.drop_index("ix_traces_run_item_id", table_name="traces")
    op.drop_table("traces")
    op.drop_index("ix_eval_run_items_run_id_status", table_name="eval_run_items")
    op.drop_index("ix_eval_run_items_run_id", table_name="eval_run_items")
    op.drop_index("ix_eval_run_items_case_id", table_name="eval_run_items")
    op.drop_table("eval_run_items")
    op.drop_index("ix_eval_runs_suite_id", table_name="eval_runs")
    op.drop_index("ix_eval_runs_status", table_name="eval_runs")
    op.drop_index("ix_eval_runs_evaluator_config_id", table_name="eval_runs")
    op.drop_index("ix_eval_runs_app_version_id", table_name="eval_runs")
    op.drop_table("eval_runs")
    op.drop_table("eval_suite_cases")
    op.drop_index("ix_eval_suites_app_id", table_name="eval_suites")
    op.drop_table("eval_suites")
    op.drop_index("ix_app_versions_app_id", table_name="app_versions")
    op.drop_table("app_versions")
    op.drop_table("embedding_cache")
    op.drop_constraint("uq_gate_rules_name", "gate_rules", type_="unique")
    op.drop_table("gate_rules")
    op.drop_index("ix_evaluator_configs_name", table_name="evaluator_configs")
    op.drop_table("evaluator_configs")
    op.drop_index("ix_eval_cases_external_id", table_name="eval_cases")
    op.drop_table("eval_cases")
    op.drop_index("ix_apps_name", table_name="apps")
    op.drop_table("apps")
