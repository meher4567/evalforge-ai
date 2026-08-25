from datetime import timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base, utc_now
from app.models import EvalRun, EvalRunItem
from app.workers.tasks import _claim_run_item, _refresh_run_progress


def _run(run_id: str) -> EvalRun:
    return EvalRun(
        id=run_id,
        app_version_id="version",
        suite_id="suite",
        evaluator_config_id="evaluators",
        status="running",
        started_at=utc_now(),
        case_count=2,
    )


def test_worker_lease_rejects_a_concurrent_delivery_and_allows_expiry():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(_run("run-1"))
        session.add(EvalRunItem(id="item-1", run_id="run-1", case_id="case-1", status="queued"))
        session.commit()

        assert _claim_run_item(
            session,
            run_item_id="item-1",
            task_id="delivery-a",
            attempt_count=1,
        )
        assert not _claim_run_item(
            session,
            run_item_id="item-1",
            task_id="delivery-b",
            attempt_count=1,
        )

        item = session.get(EvalRunItem, "item-1")
        assert item is not None
        item.lease_expires_at = utc_now() - timedelta(seconds=1)
        session.commit()

        assert _claim_run_item(
            session,
            run_item_id="item-1",
            task_id="delivery-b",
            attempt_count=2,
        )

    engine.dispose()


def test_progress_recount_is_idempotent():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(_run("run-2"))
        session.add_all(
            [
                EvalRunItem(
                    id="item-2a",
                    run_id="run-2",
                    case_id="case-2a",
                    status="completed",
                ),
                EvalRunItem(
                    id="item-2b",
                    run_id="run-2",
                    case_id="case-2b",
                    status="errored",
                ),
            ]
        )
        session.commit()

        _refresh_run_progress(session, "run-2")
        _refresh_run_progress(session, "run-2")
        session.expire_all()
        run = session.get(EvalRun, "run-2")
        assert run is not None
        assert run.case_completed == 1
        assert run.case_errored == 1

    engine.dispose()
