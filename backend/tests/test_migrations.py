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
