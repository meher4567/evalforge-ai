from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AppCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = ""


class AppRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: str
    created_at: datetime


class AppVersionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    adapter_module: str = Field(min_length=1, max_length=255)
    config: dict[str, Any] = Field(default_factory=dict)


class AppVersionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    app_id: str
    name: str
    adapter_module: str
    config: dict[str, Any]
    created_at: datetime


class EvalSuiteCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class EvalSuiteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    app_id: str
    name: str
    created_at: datetime


class EvalCaseImportItem(BaseModel):
    external_id: str | None = None
    payload: dict[str, Any]


class EvalCaseImportRequest(BaseModel):
    cases: list[EvalCaseImportItem] = Field(min_length=1)


class EvalCaseImportResult(BaseModel):
    imported: int
    errors: list[str]


class EvalCaseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    external_id: str | None
    payload: dict[str, Any]
    created_at: datetime


class EvalSuiteSummary(BaseModel):
    case_count: int
    tag_distribution: dict[str, int]


class EvaluatorConfigCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    config: dict[str, Any]


class EvaluatorConfigRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    config: dict[str, Any]
    created_at: datetime
