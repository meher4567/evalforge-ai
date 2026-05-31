from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, new_uuid, utc_now


class App(Base):
    __tablename__ = "apps"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    name: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    versions: Mapped[list[AppVersion]] = relationship(
        back_populates="app",
        cascade="all, delete-orphan",
    )
    suites: Mapped[list[EvalSuite]] = relationship(
        back_populates="app",
        cascade="all, delete-orphan",
    )


class AppVersion(Base):
    __tablename__ = "app_versions"
    __table_args__ = (UniqueConstraint("app_id", "name", name="uq_app_versions_app_id_name"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    app_id: Mapped[str] = mapped_column(ForeignKey("apps.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    config: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    adapter_module: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    app: Mapped[App] = relationship(back_populates="versions")


class EvalSuite(Base):
    __tablename__ = "eval_suites"
    __table_args__ = (UniqueConstraint("app_id", "name", name="uq_eval_suites_app_id_name"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    app_id: Mapped[str] = mapped_column(ForeignKey("apps.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    app: Mapped[App] = relationship(back_populates="suites")
    suite_cases: Mapped[list[EvalSuiteCase]] = relationship(
        back_populates="suite",
        cascade="all, delete-orphan",
    )


class EvalCase(Base):
    __tablename__ = "eval_cases"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    suite_links: Mapped[list[EvalSuiteCase]] = relationship(
        back_populates="case",
        cascade="all, delete-orphan",
    )


class EvalSuiteCase(Base):
    __tablename__ = "eval_suite_cases"

    suite_id: Mapped[str] = mapped_column(
        ForeignKey("eval_suites.id", ondelete="CASCADE"),
        primary_key=True,
    )
    case_id: Mapped[str] = mapped_column(
        ForeignKey("eval_cases.id", ondelete="CASCADE"),
        primary_key=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    suite: Mapped[EvalSuite] = relationship(back_populates="suite_cases")
    case: Mapped[EvalCase] = relationship(back_populates="suite_links")


class EvaluatorConfig(Base):
    __tablename__ = "evaluator_configs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    name: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    config: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class EvalRun(Base):
    __tablename__ = "eval_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    app_version_id: Mapped[str] = mapped_column(ForeignKey("app_versions.id"), index=True)
    suite_id: Mapped[str] = mapped_column(ForeignKey("eval_suites.id"), index=True)
    evaluator_config_id: Mapped[str] = mapped_column(ForeignKey("evaluator_configs.id"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    case_count: Mapped[int] = mapped_column(Integer, default=0)
    case_completed: Mapped[int] = mapped_column(Integer, default=0)
    case_errored: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class EvalRunItem(Base):
    __tablename__ = "eval_run_items"
    __table_args__ = (
        UniqueConstraint("run_id", "case_id", name="uq_eval_run_items_run_id_case_id"),
        Index("ix_eval_run_items_run_id_status", "run_id", "status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    run_id: Mapped[str] = mapped_column(ForeignKey("eval_runs.id", ondelete="CASCADE"), index=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("eval_cases.id"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="queued")
    attempt_count: Mapped[int] = mapped_column(Integer, default=1)
    recorded_latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    recorded_cost_usd: Mapped[float | None] = mapped_column(Numeric(10, 6), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Trace(Base):
    __tablename__ = "traces"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    run_item_id: Mapped[str] = mapped_column(
        ForeignKey("eval_run_items.id", ondelete="CASCADE"),
        unique=True,
        index=True,
    )
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class EvalResult(Base):
    __tablename__ = "eval_results"
    __table_args__ = (
        Index("ix_eval_results_run_item_id_evaluator_name", "run_item_id", "evaluator_name"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    run_item_id: Mapped[str] = mapped_column(
        ForeignKey("eval_run_items.id", ondelete="CASCADE"),
        index=True,
    )
    evaluator_name: Mapped[str] = mapped_column(String(120))
    score: Mapped[float | None] = mapped_column(Numeric(10, 6), nullable=True)
    passed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    errored: Mapped[bool] = mapped_column(Boolean, default=False)
    skipped: Mapped[bool] = mapped_column(Boolean, default=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class GateRule(Base):
    __tablename__ = "gate_rules"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    rules: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class Comparison(Base):
    __tablename__ = "comparisons"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    baseline_run_id: Mapped[str] = mapped_column(ForeignKey("eval_runs.id"), index=True)
    candidate_run_id: Mapped[str] = mapped_column(ForeignKey("eval_runs.id"), index=True)
    gate_rules_id: Mapped[str] = mapped_column(ForeignKey("gate_rules.id"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class RegressionReport(Base):
    __tablename__ = "regression_reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    comparison_id: Mapped[str] = mapped_column(
        ForeignKey("comparisons.id", ondelete="CASCADE"),
        unique=True,
    )
    metrics: Mapped[dict[str, Any]] = mapped_column(JSON)
    gate_verdict: Mapped[str] = mapped_column(String(20))
    gate_reasons: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class GoldLabel(Base):
    __tablename__ = "gold_labels"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    case_id: Mapped[str] = mapped_column(ForeignKey("eval_cases.id"), index=True)
    version_id: Mapped[str] = mapped_column(ForeignKey("app_versions.id"), index=True)
    run_item_id: Mapped[str | None] = mapped_column(ForeignKey("eval_run_items.id"), nullable=True)
    output_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    label_score: Mapped[int] = mapped_column(Integer)
    labeler_id: Mapped[str] = mapped_column(String(120), default="self")
    rubric_version: Mapped[str] = mapped_column(String(40), default="v1")
    labeled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
