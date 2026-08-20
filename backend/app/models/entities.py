from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
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

from app.core.tenancy import DEFAULT_ORGANIZATION_ID
from app.db.base import Base, new_uuid, utc_now


class User(Base):
    __tablename__ = "users"
    __table_args__ = (CheckConstraint("status IN ('active', 'disabled')", name="ck_users_status"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active", index=True)
    failed_login_attempts: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    name: Mapped[str] = mapped_column(String(120))
    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class OidcIdentity(Base):
    __tablename__ = "oidc_identities"
    __table_args__ = (
        UniqueConstraint("issuer", "subject", name="uq_oidc_identities_issuer_subject"),
        UniqueConstraint("user_id", "issuer", name="uq_oidc_identities_user_issuer"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    issuer: Mapped[str] = mapped_column(String(512))
    subject: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class Membership(Base):
    __tablename__ = "memberships"
    __table_args__ = (
        CheckConstraint(
            "role IN ('owner', 'admin', 'evaluator', 'viewer')",
            name="ck_memberships_role",
        ),
    )

    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    role: Mapped[str] = mapped_column(String(20), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class AuthSession(Base):
    __tablename__ = "auth_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class PersonalApiKey(Base):
    __tablename__ = "personal_api_keys"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "organization_id",
            "name",
            name="uq_personal_api_keys_user_org_name",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(120))
    key_prefix: Mapped[str] = mapped_column(String(16), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class App(Base):
    __tablename__ = "apps"
    __table_args__ = (
        UniqueConstraint("organization_id", "name", name="uq_apps_organization_id_name"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id"), default=DEFAULT_ORGANIZATION_ID, index=True
    )
    name: Mapped[str] = mapped_column(String(120))
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
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "name",
            name="uq_evaluator_configs_organization_id_name",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id"), default=DEFAULT_ORGANIZATION_ID, index=True
    )
    name: Mapped[str] = mapped_column(String(120))
    config: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class EvalRun(Base):
    __tablename__ = "eval_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id"), default=DEFAULT_ORGANIZATION_ID, index=True
    )
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
    worker_task_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
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
        UniqueConstraint(
            "run_item_id",
            "evaluator_name",
            name="uq_eval_results_run_item_id_evaluator_name",
        ),
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
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "name",
            name="uq_gate_rules_organization_id_name",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id"), default=DEFAULT_ORGANIZATION_ID, index=True
    )
    name: Mapped[str] = mapped_column(String(120))
    rules: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class Comparison(Base):
    __tablename__ = "comparisons"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id"), default=DEFAULT_ORGANIZATION_ID, index=True
    )
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
