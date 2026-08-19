"""Конфигурация Robot WS Bridge.

Конфигурация задаётся через переменные окружения, чтобы на роботе было удобно
переопределять порты/топики без пересборки образа.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class AppConfig:
    """Параметры приложения, считываемые из окружения."""

    ws_host: str
    ws_port: int
    ws_auth_token: str
    cmd_vel_topic: str
    mock_status_tick_ms: int
    fsm_state_url: str
    battery_topic: str
    robot_mode_topic: str


def _get_env(name: str, default: str | None = None) -> str:
    """Возвращает значение переменной окружения.

    Args:
        name: Имя переменной окружения.
        default: Значение по умолчанию, если переменная не задана.

    Returns:
        Значение переменной окружения.

    Raises:
        ValueError: Если переменная не задана и default не указан.
    """
    value = os.getenv(name)
    if value is None:
        if default is None:
            raise ValueError(f"Переменная окружения {name} не задана")
        return default
    return value


def load_config() -> AppConfig:
    """Загружает конфигурацию из переменных окружения.

    Returns:
        Сформированная конфигурация приложения.
    """
    ws_host = os.getenv("WS_HOST", "0.0.0.0")
    ws_port = int(os.getenv("WS_PORT", "8765"))
    ws_auth_token = _get_env("WS_AUTH_TOKEN")
    cmd_vel_topic = os.getenv("CMD_VEL_TOPIC", "/cmd_vel")
    mock_status_tick_ms = int(os.getenv("MOCK_STATUS_TICK_MS", "500"))
    fsm_state_url = os.getenv("FSM_STATE_URL", "http://10.18.14.150:8080/api/fsm")
    battery_topic = os.getenv("BATTERY_TOPIC", "/battery_state")
    robot_mode_topic = os.getenv("ROBOT_MODE_TOPIC", "")

    return AppConfig(
        ws_host=ws_host,
        ws_port=ws_port,
        ws_auth_token=ws_auth_token,
        cmd_vel_topic=cmd_vel_topic,
        mock_status_tick_ms=mock_status_tick_ms,
        fsm_state_url=fsm_state_url,
        battery_topic=battery_topic,
        robot_mode_topic=robot_mode_topic,
    )

