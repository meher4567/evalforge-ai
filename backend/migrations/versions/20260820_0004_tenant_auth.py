"""Add organizations, users, RBAC memberships and opaque credentials.

Revision ID: 20260820_0004
Revises: 20260820_0003
Create Date: 2026-08-20
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260820_0004"
down_revision = "20260820_0003"
branch_labels = None
depends_on = None

DEFAULT_ORGANIZATION_ID = "00000000-0000-0000-0000-000000000001"


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_organizations_slug", "organizations", ["slug"], unique=True)
    op.execute(
        sa.text(
            "INSERT INTO organizations (id, name, slug, created_at) "
            "VALUES (:id, 'Default Workspace', 'default', CURRENT_TIMESTAMP)"
        ).bindparams(id=DEFAULT_ORGANIZATION_ID)
    )

    op.create_table(
        "users",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("display_name", sa.String(length=120), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("failed_login_attempts", sa.Integer(), nullable=False),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("status IN ('active', 'disabled')", name="ck_users_status"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_status", "users", ["status"])
    op.create_index("ix_users_locked_until", "users", ["locked_until"])

    op.create_table(
        "oidc_identities",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(length=36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("issuer", sa.String(length=512), nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "issuer",
            "subject",
            name="uq_oidc_identities_issuer_subject",
        ),
        sa.UniqueConstraint(
            "user_id",
            "issuer",
            name="uq_oidc_identities_user_issuer",
        ),
    )
    op.create_index("ix_oidc_identities_user_id", "oidc_identities", ["user_id"])

    op.create_table(
        "memberships",
        sa.Column(
            "organization_id",
            sa.String(length=36),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "user_id",
            sa.String(length=36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "role IN ('owner', 'admin', 'evaluator', 'viewer')",
            name="ck_memberships_role",
        ),
    )
    op.create_index("ix_memberships_role", "memberships", ["role"])

    op.create_table(
        "auth_sessions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(length=36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "organization_id",
            sa.String(length=36),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_auth_sessions_user_id", "auth_sessions", ["user_id"])
    op.create_index("ix_auth_sessions_organization_id", "auth_sessions", ["organization_id"])
    op.create_index("ix_auth_sessions_token_hash", "auth_sessions", ["token_hash"], unique=True)
    op.create_index("ix_auth_sessions_expires_at", "auth_sessions", ["expires_at"])

    op.create_table(
        "personal_api_keys",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(length=36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "organization_id",
            sa.String(length=36),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("key_prefix", sa.String(length=16), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "user_id",
            "organization_id",
            "name",
            name="uq_personal_api_keys_user_org_name",
        ),
    )
    op.create_index("ix_personal_api_keys_user_id", "personal_api_keys", ["user_id"])
    op.create_index(
        "ix_personal_api_keys_organization_id",
        "personal_api_keys",
        ["organization_id"],
    )
    op.create_index("ix_personal_api_keys_key_prefix", "personal_api_keys", ["key_prefix"])
    op.create_index(
        "ix_personal_api_keys_token_hash",
        "personal_api_keys",
        ["token_hash"],
        unique=True,
    )

    for table in ("apps", "evaluator_configs", "gate_rules", "eval_runs", "comparisons"):
        op.add_column(table, sa.Column("organization_id", sa.String(length=36), nullable=True))
        op.execute(
            sa.text(f"UPDATE {table} SET organization_id = :organization_id").bindparams(
                organization_id=DEFAULT_ORGANIZATION_ID
            )
        )
        op.alter_column(table, "organization_id", nullable=False)
        op.create_foreign_key(
            f"fk_{table}_organization_id",
            table,
            "organizations",
            ["organization_id"],
            ["id"],
        )
        op.create_index(f"ix_{table}_organization_id", table, ["organization_id"])

    op.drop_index("ix_apps_name", table_name="apps")
    op.create_unique_constraint("uq_apps_organization_id_name", "apps", ["organization_id", "name"])
    op.drop_index("ix_evaluator_configs_name", table_name="evaluator_configs")
    op.create_unique_constraint(
        "uq_evaluator_configs_organization_id_name",
        "evaluator_configs",
        ["organization_id", "name"],
    )
    op.drop_constraint("uq_gate_rules_name", "gate_rules", type_="unique")
    op.create_unique_constraint(
        "uq_gate_rules_organization_id_name",
        "gate_rules",
        ["organization_id", "name"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_gate_rules_organization_id_name", "gate_rules", type_="unique")
    op.create_unique_constraint("uq_gate_rules_name", "gate_rules", ["name"])
    op.drop_constraint(
        "uq_evaluator_configs_organization_id_name",
        "evaluator_configs",
        type_="unique",
    )
    op.create_index("ix_evaluator_configs_name", "evaluator_configs", ["name"], unique=True)
    op.drop_constraint("uq_apps_organization_id_name", "apps", type_="unique")
    op.create_index("ix_apps_name", "apps", ["name"], unique=True)

    for table in ("comparisons", "eval_runs", "gate_rules", "evaluator_configs", "apps"):
        op.drop_index(f"ix_{table}_organization_id", table_name=table)
        op.drop_constraint(f"fk_{table}_organization_id", table, type_="foreignkey")
        op.drop_column(table, "organization_id")

    op.drop_table("personal_api_keys")
    op.drop_table("auth_sessions")
    op.drop_index("ix_memberships_role", table_name="memberships")
    op.drop_table("memberships")
    op.drop_index("ix_oidc_identities_user_id", table_name="oidc_identities")
    op.drop_table("oidc_identities")
    op.drop_index("ix_users_status", table_name="users")
    op.drop_index("ix_users_locked_until", table_name="users")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
    op.drop_index("ix_organizations_slug", table_name="organizations")
    op.drop_table("organizations")
