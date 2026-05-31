from collections.abc import Callable
from importlib import import_module
from typing import Any

from app.adapters.base import AdapterOutput

AdapterFn = Callable[[str, dict[str, Any]], AdapterOutput]


def load_adapter(module_path: str) -> AdapterFn:
    module = import_module(module_path)
    adapter = getattr(module, "run", None)
    if adapter is None or not callable(adapter):
        raise ValueError(f"Adapter module {module_path} does not expose callable run()")
    return adapter
