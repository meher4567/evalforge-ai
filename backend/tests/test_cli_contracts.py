import inspect

from app.cli import run as run_cli


def test_run_cli_uses_existing_session_factory_name():
    source = inspect.getsource(run_cli.run_evals)

    assert "from app.db.session import SessionLocal" in source
    assert "async_session_factory" not in source
