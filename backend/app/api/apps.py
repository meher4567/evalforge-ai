from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.models import App, AppVersion, EvalSuite
from app.schemas import (
    AppCreate,
    AppRead,
    AppVersionCreate,
    AppVersionRead,
    EvalSuiteCreate,
    EvalSuiteRead,
)

router = APIRouter(prefix="/api/apps", tags=["apps"])
SessionDep = Annotated[AsyncSession, Depends(get_session)]


@router.post("", response_model=AppRead, status_code=status.HTTP_201_CREATED)
async def create_app(payload: AppCreate, session: SessionDep) -> App:
    existing = await session.scalar(select(App).where(App.name == payload.name))
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="App name already exists",
        )

    app = App(name=payload.name, description=payload.description)
    session.add(app)
    await session.commit()
    await session.refresh(app)
    return app


@router.get("", response_model=list[AppRead])
async def list_apps(session: SessionDep) -> list[App]:
    result = await session.scalars(select(App).order_by(App.created_at.desc()))
    return list(result)


@router.get("/{app_id}", response_model=AppRead)
async def get_app(app_id: str, session: SessionDep) -> App:
    app = await session.get(App, app_id)
    if app is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="App not found")
    return app


@router.post(
    "/{app_id}/versions",
    response_model=AppVersionRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_app_version(
    app_id: str,
    payload: AppVersionCreate,
    session: SessionDep,
) -> AppVersion:
    app = await session.get(App, app_id)
    if app is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="App not found")

    existing = await session.scalar(
        select(AppVersion).where(AppVersion.app_id == app_id, AppVersion.name == payload.name)
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="App version name already exists",
        )

    version = AppVersion(
        app_id=app_id,
        name=payload.name,
        adapter_module=payload.adapter_module,
        config=payload.config,
    )
    session.add(version)
    await session.commit()
    await session.refresh(version)
    return version


@router.get("/{app_id}/versions", response_model=list[AppVersionRead])
async def list_app_versions(
    app_id: str,
    session: SessionDep,
) -> list[AppVersion]:
    result = await session.scalars(
        select(AppVersion).where(AppVersion.app_id == app_id).order_by(AppVersion.created_at.desc())
    )
    return list(result)


@router.post("/{app_id}/suites", response_model=EvalSuiteRead, status_code=status.HTTP_201_CREATED)
async def create_eval_suite(
    app_id: str,
    payload: EvalSuiteCreate,
    session: SessionDep,
) -> EvalSuite:
    app = await session.get(App, app_id)
    if app is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="App not found")

    existing = await session.scalar(
        select(EvalSuite).where(EvalSuite.app_id == app_id, EvalSuite.name == payload.name)
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Eval suite name already exists",
        )

    suite = EvalSuite(app_id=app_id, name=payload.name)
    session.add(suite)
    await session.commit()
    await session.refresh(suite)
    return suite
