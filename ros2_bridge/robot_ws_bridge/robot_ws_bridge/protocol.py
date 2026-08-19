"""Типы и валидация протокола Robot WS Bridge (v1)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class ProtocolError(Exception):
    """Ошибка валидации протокола."""

    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None) -> None:
        """Создаёт ошибку протокола.

        Args:
            code: Машинный код ошибки.
            message: Человекочитаемое описание.
            details: Дополнительные детали (структурированный JSON-объект).
        """
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


@dataclass(frozen=True)
class Vector3:
    """Вектор 3D."""

    x: float
    y: float
    z: float


@dataclass(frozen=True)
class Twist:
    """Линейная и угловая скорость."""

    linear: Vector3
    angular: Vector3


@dataclass(frozen=True)
class TeleopCommand:
    """Команда управления движением."""

    ts: int | None
    twist: Twist


def _as_float(value: Any, *, path: str) -> float:
    """Преобразует значение в float.

    Args:
        value: Любое значение, ожидаем число.
        path: Путь поля для диагностики.

    Returns:
        Значение float.

    Raises:
        ProtocolError: Если значение не число.
    """
    if isinstance(value, (int, float)):
        return float(value)
    raise ProtocolError("VALIDATION_ERROR", f"Поле {path} должно быть числом", {"path": path})


def _get(obj: dict[str, Any], key: str, *, default: Any = None) -> Any:
    """Безопасный доступ к ключу в dict."""
    return obj[key] if key in obj else default


def parse_teleop(message: dict[str, Any]) -> TeleopCommand:
    """Парсит команду `teleop` протокола v1.

    Args:
        message: JSON объект сообщения.

    Returns:
        Структурированная команда teleop.

    Raises:
        ProtocolError: Если сообщение не соответствует ожидаемой схеме.
    """
    twist_obj = message.get("twist")
    if not isinstance(twist_obj, dict):
        raise ProtocolError("VALIDATION_ERROR", "Поле twist обязательно и должно быть объектом", {"path": "twist"})

    linear_obj = _get(twist_obj, "linear", default={})
    angular_obj = _get(twist_obj, "angular", default={})
    if not isinstance(linear_obj, dict) or not isinstance(angular_obj, dict):
        raise ProtocolError(
            "VALIDATION_ERROR",
            "Поля twist.linear и twist.angular должны быть объектами",
            {"path": "twist"},
        )

    linear = Vector3(
        x=_as_float(_get(linear_obj, "x", default=0.0), path="twist.linear.x"),
        y=_as_float(_get(linear_obj, "y", default=0.0), path="twist.linear.y"),
        z=_as_float(_get(linear_obj, "z", default=0.0), path="twist.linear.z"),
    )
    angular = Vector3(
        x=_as_float(_get(angular_obj, "x", default=0.0), path="twist.angular.x"),
        y=_as_float(_get(angular_obj, "y", default=0.0), path="twist.angular.y"),
        z=_as_float(_get(angular_obj, "z", default=0.0), path="twist.angular.z"),
    )

    ts = message.get("ts")
    if ts is not None and not isinstance(ts, int):
        raise ProtocolError("VALIDATION_ERROR", "Поле ts должно быть int, если задано", {"path": "ts"})

    return TeleopCommand(ts=ts, twist=Twist(linear=linear, angular=angular))


def make_ack(*, request_id: str | None = None, ts: int | None = None) -> dict[str, Any]:
    """Формирует ответ `ack`."""
    payload: dict[str, Any] = {"type": "ack"}
    if request_id is not None:
        payload["requestId"] = request_id
    if ts is not None:
        payload["ts"] = ts
    return payload


def make_error(err: ProtocolError) -> dict[str, Any]:
    """Формирует ответ `error`."""
    return {"type": "error", "code": err.code, "message": err.message, "details": err.details}

