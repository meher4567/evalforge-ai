from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class EvaluationResult:
    evaluator_name: str
    score: float | None
    passed: bool | None
    details: dict[str, Any] = field(default_factory=dict)
    errored: bool = False
    skipped: bool = False
    error_message: str | None = None
