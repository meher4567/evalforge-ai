from collections.abc import Callable
from importlib import import_module
from typing import Any

from app.adapters.base import AdapterOutput
from app.core.config import get_settings

AdapterFn = Callable[[str, dict[str, Any]], AdapterOutput]


def load_adapter(module_path: str) -> AdapterFn:
    validate_adapter_module(module_path)
    module = import_module(module_path)
    adapter = getattr(module, "run", None)
    if adapter is None or not callable(adapter):
        raise ValueError(f"Adapter module {module_path} does not expose callable run()")
    return adapter


def validate_adapter_module(module_path: str) -> None:
    allowed_modules = {
        item.strip() for item in get_settings().allowed_adapter_modules.split(",") if item.strip()
    }
    if module_path not in allowed_modules:
        raise ValueError(
            f"Adapter module {module_path!r} is not allowed; configure "
            "EVALFORGE_ALLOWED_ADAPTER_MODULES to opt in"
        )
