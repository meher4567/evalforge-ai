from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class AdapterOutput:
    answer: str
    retrieved_chunks: list[dict[str, Any]]
    prompt_used: str
    model_used: str
    latency_ms: int
    estimated_cost_usd: float
    trace_steps: list[dict[str, Any]]
