"""Small subset of the Pydantic API required for tests."""

from __future__ import annotations

import os
from typing import Any, Callable, Dict, Iterable, List, Optional


class _Missing:
    pass


MISSING = _Missing()


class FieldInfo:
    def __init__(
        self,
        default: Any = MISSING,
        *,
        default_factory: Optional[Callable[[], Any]] = None,
        env: Optional[str] = None,
        description: str | None = None,
        exclude: bool = False,
    ) -> None:
        self.default = default
        self.default_factory = default_factory
        self.env = env
        self.description = description
        self.exclude = exclude


def Field(
    default: Any = MISSING,
    *,
    default_factory: Optional[Callable[[], Any]] = None,
    env: Optional[str] = None,
    description: str | None = None,
    exclude: bool = False,
) -> FieldInfo:
    return FieldInfo(
        default=default,
        default_factory=default_factory,
        env=env,
        description=description,
        exclude=exclude,
    )


def validator(*field_names: str, pre: bool = False, always: bool = False):  # pragma: no cover - decoration is straightforward
    def decorator(func: Callable[[Any, Any], Any]) -> Callable[[Any, Any], Any]:
        func._validator_fields = field_names  # type: ignore[attr-defined]
        func._validator_kwargs = {"pre": pre, "always": always}  # type: ignore[attr-defined]
        return func

    return decorator


class ModelMeta(type):
    def __new__(mcls, name: str, bases: tuple[type, ...], namespace: Dict[str, Any]):
        validators: List[Callable[[Any, Any], Any]] = []
        for value in namespace.values():
            if callable(value) and hasattr(value, "_validator_fields"):
                validators.append(value)
        namespace["_validators"] = validators
        return super().__new__(mcls, name, bases, namespace)


class BaseModel(metaclass=ModelMeta):
    """Very small replacement for ``pydantic.BaseModel``."""

    def __init__(self, **data: Any) -> None:
        self._apply_fields(data)
        self._run_validators()

    def _apply_fields(self, data: Dict[str, Any]) -> None:
        annotations: Dict[str, Any] = getattr(self.__class__, "__annotations__", {})
        remaining = dict(data)
        for name in annotations:
            value = remaining.pop(name, MISSING)
            field_info = getattr(self.__class__, name, MISSING)
            if isinstance(field_info, FieldInfo):
                if value is MISSING:
                    value = self._default_value(field_info)
            else:
                if value is MISSING and field_info is not MISSING:
                    value = field_info
            if value is MISSING:
                raise TypeError(f"Missing required field: {name}")
            setattr(self, name, value)
        for key, value in remaining.items():  # pragma: no cover - defensive
            setattr(self, key, value)

    def _default_value(self, field_info: FieldInfo) -> Any:
        if field_info.default_factory is not None:
            return field_info.default_factory()
        if field_info.default is not MISSING and field_info.default is not ...:
            return field_info.default
        return MISSING

    def _run_validators(self) -> None:
        for func in getattr(self, "_validators", []):
            fields = getattr(func, "_validator_fields", ())
            for field_name in fields:
                current_value = getattr(self, field_name)
                new_value = func(self.__class__, current_value)
                setattr(self, field_name, new_value)

    def dict(self, *, include_excluded: bool = False) -> Dict[str, Any]:  # pragma: no cover - not used in tests
        output: Dict[str, Any] = {}
        annotations: Dict[str, Any] = getattr(self.__class__, "__annotations__", {})
        for name in annotations:
            field_info = getattr(self.__class__, name, MISSING)
            if isinstance(field_info, FieldInfo) and field_info.exclude and not include_excluded:
                continue
            output[name] = getattr(self, name)
        return output


class BaseSettings(BaseModel):
    """Simplified ``BaseSettings`` that honours environment overrides."""

    def __init__(self, **overrides: Any) -> None:
        env_overrides: Dict[str, Any] = {}
        annotations: Dict[str, Any] = getattr(self.__class__, "__annotations__", {})
        for name in annotations:
            field_info = getattr(self.__class__, name, MISSING)
            if isinstance(field_info, FieldInfo) and field_info.env:
                value = os.getenv(field_info.env)
                if value is not None and name not in overrides:
                    env_overrides[name] = value
        merged = {**env_overrides, **overrides}
        super().__init__(**merged)


__all__ = ["BaseModel", "BaseSettings", "Field", "validator"]
