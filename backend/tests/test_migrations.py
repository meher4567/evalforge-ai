import ast
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]


def test_alembic_project_files_exist():
    assert (BACKEND_ROOT / "alembic.ini").exists()
    assert (BACKEND_ROOT / "migrations" / "env.py").exists()
    assert (BACKEND_ROOT / "migrations" / "script.py.mako").exists()


def test_initial_migration_defines_core_tables():
    versions = list((BACKEND_ROOT / "migrations" / "versions").glob("*initial*.py"))
    assert versions, "Expected an initial Alembic migration"

    migration_tree = ast.parse(versions[0].read_text(encoding="utf-8"))
    created_tables = {
        node.args[0].value
        for node in ast.walk(migration_tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "create_table"
        and node.args
        and isinstance(node.args[0], ast.Constant)
    }
    for table_name in [
        "apps",
        "app_versions",
        "eval_cases",
        "eval_runs",
        "eval_run_items",
        "eval_results",
        "traces",
        "comparisons",
        "regression_reports",
        "gold_labels",
        "embedding_cache",
    ]:
        assert table_name in created_tables


def test_alembic_env_uses_application_settings_and_metadata():
    env_text = (BACKEND_ROOT / "migrations" / "env.py").read_text(encoding="utf-8")

    assert "get_settings" in env_text
    assert "Base.metadata" in env_text
    assert "target_metadata" in env_text


def test_worker_lease_migration_follows_initial_schema():
    migration = BACKEND_ROOT / "migrations" / "versions" / "20260820_0002_worker_leases.py"
    source = migration.read_text(encoding="utf-8")

    assert 'down_revision = "20260605_0001"' in source
    assert '"worker_task_id"' in source
    assert '"lease_expires_at"' in source


def test_unique_result_migration_follows_worker_leases():
    migration = BACKEND_ROOT / "migrations" / "versions" / "20260820_0003_unique_eval_results.py"
    source = migration.read_text(encoding="utf-8")

    assert 'down_revision = "20260820_0002"' in source
    assert '"uq_eval_results_run_item_id_evaluator_name"' in source
    assert '"run_item_id", "evaluator_name"' in source


def test_tenant_auth_migration_follows_unique_results():
    migration = BACKEND_ROOT / "migrations" / "versions" / "20260820_0004_tenant_auth.py"
    source = migration.read_text(encoding="utf-8")

    assert 'down_revision = "20260820_0003"' in source
    for table_name in [
        "organizations",
        "users",
        "memberships",
        "auth_sessions",
        "personal_api_keys",
        "oidc_identities",
    ]:
        assert f'"{table_name}"' in source
    assert '"organization_id"' in source
