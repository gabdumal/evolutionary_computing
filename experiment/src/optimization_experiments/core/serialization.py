from __future__ import annotations

from dataclasses import fields, is_dataclass
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping


def to_primitive(value: Any) -> Any:
    """Convert API objects to deterministic JSON-compatible primitives."""
    if is_dataclass(value):
        return {
            field.name: to_primitive(getattr(value, field.name))
            for field in fields(value)
        }
    if isinstance(value, MappingProxyType):
        value = dict(value)
    if isinstance(value, Mapping):
        return {
            str(key): to_primitive(item)
            for key, item in sorted(value.items(), key=lambda item: str(item[0]))
        }
    if isinstance(value, (tuple, list)):
        return [to_primitive(item) for item in value]
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, type):
        return f"{value.__module__}.{value.__qualname__}"
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    raise TypeError(f"Unsupported value for serialization: {type(value)!r}.")
