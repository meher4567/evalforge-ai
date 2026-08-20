from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.loader import validate_adapter_module
from app.core.auth import get_current_principal
from app.core.tenancy import Principal, require_role
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
PrincipalDep = Annotated[Principal, Depends(get_current_principal)]


@router.post("", response_model=AppRead, status_code=status.HTTP_201_CREATED)
async def create_app(payload: AppCreate, principal: PrincipalDep, session: SessionDep) -> App:
    require_role(principal, "evaluator")
    existing = await session.scalar(
        select(App).where(
            App.organization_id == principal.organization_id,
            App.name == payload.name,
        )
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="App name already exists",
        )

    app = App(
        organization_id=principal.organization_id,
        name=payload.name,
        description=payload.description,
    )
    session.add(app)
    await session.commit()
    await session.refresh(app)
    return app


@router.get("", response_model=list[AppRead])
async def list_apps(
    session: SessionDep,
    principal: PrincipalDep,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[App]:
    result = await session.scalars(
        select(App)
        .where(App.organization_id == principal.organization_id)
        .order_by(App.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result)


@router.get("/{app_id}", response_model=AppRead)
async def get_app(app_id: str, principal: PrincipalDep, session: SessionDep) -> App:
    app = await _tenant_app(session, app_id, principal.organization_id)
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
    principal: PrincipalDep,
    session: SessionDep,
) -> AppVersion:
    require_role(principal, "evaluator")
    app = await _tenant_app(session, app_id, principal.organization_id)
    if app is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="App not found")

    try:
        validate_adapter_module(payload.adapter_module)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc

    inline_secret_keys = _find_inline_secret_keys(payload.config)
    if inline_secret_keys:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                "Inline secrets are not accepted in version config; use an approved "
                "environment variable instead"
            ),
        )

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
    principal: PrincipalDep,
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[AppVersion]:
    if await _tenant_app(session, app_id, principal.organization_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="App not found")
    result = await session.scalars(
        select(AppVersion)
        .where(AppVersion.app_id == app_id)
        .order_by(AppVersion.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result)


@router.get("/{app_id}/suites", response_model=list[EvalSuiteRead])
async def list_eval_suites(
    app_id: str,
    principal: PrincipalDep,
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[EvalSuite]:
    if await _tenant_app(session, app_id, principal.organization_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="App not found")
    result = await session.scalars(
        select(EvalSuite)
        .where(EvalSuite.app_id == app_id)
        .order_by(EvalSuite.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result)


@router.post("/{app_id}/suites", response_model=EvalSuiteRead, status_code=status.HTTP_201_CREATED)
async def create_eval_suite(
    app_id: str,
    payload: EvalSuiteCreate,
    principal: PrincipalDep,
    session: SessionDep,
) -> EvalSuite:
    require_role(principal, "evaluator")
    app = await _tenant_app(session, app_id, principal.organization_id)
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


async def _tenant_app(
    session: AsyncSession,
    app_id: str,
    organization_id: str,
) -> App | None:
    return await session.scalar(
        select(App).where(App.id == app_id, App.organization_id == organization_id)
    )


def _find_inline_secret_keys(value: object, path: str = "config") -> list[str]:
    secret_names = {
        "api_key",
        "apikey",
        "authorization",
        "password",
        "secret",
        "client_secret",
        "token",
        "access_token",
        "bearer_token",
        "credential",
        "credentials",
    }
    found: list[str] = []
    if isinstance(value, dict):
        for key, nested in value.items():
            nested_path = f"{path}.{key}"
            normalized_key = str(key).strip().lower().replace("-", "_")
            if normalized_key in secret_names:
                found.append(nested_path)
            found.extend(_find_inline_secret_keys(nested, nested_path))
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            found.extend(_find_inline_secret_keys(nested, f"{path}[{index}]"))
    return found
