"""Источники статусов робота."""

from __future__ import annotations

import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class StatusMessage:
    """Сообщение статуса, которое будет отправлено в WS."""

    topic: str
    ts: int
    data: dict[str, Any]


class StatusSource(ABC):
    """Абстракция источника статусов робота."""

    @abstractmethod
    def get_snapshot(self) -> dict[str, Any]:
        """Возвращает мгновенный снимок состояния.

        Returns:
            Объект `data` для сообщения `state_snapshot`.
        """

    @abstractmethod
    def poll(self) -> list[StatusMessage]:
        """Возвращает список событий статуса, накопленных с прошлого вызова.

        Returns:
            Список сообщений статуса.
        """


class RosStatusSource(StatusSource):
    """Реальный источник статусов из ROS2 callbacks."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._latest_battery: dict[str, Any] = {}
        self._latest_robot_state: dict[str, Any] = {}
        self._queue: list[StatusMessage] = []

    def update_battery(self, level: float, ts_ms: int) -> None:
        """Обновляет батарею из ROS2 топика."""
        data = {"level": float(level)}
        with self._lock:
            self._latest_battery = data
            self._queue.append(StatusMessage(topic="battery", ts=ts_ms, data=data))

    def update_robot_state(self, mode: str, ts_ms: int) -> None:
        """Обновляет режим робота из ROS2 топика (если подключен)."""
        data = {"mode": mode, "ts": ts_ms}
        with self._lock:
            self._latest_robot_state = data
            self._queue.append(StatusMessage(topic="robot_state", ts=ts_ms, data=data))

    def get_snapshot(self) -> dict[str, Any]:
        """Возвращает последний известный снимок состояния."""
        with self._lock:
            snapshot: dict[str, Any] = {}
            if self._latest_battery:
                snapshot["battery"] = dict(self._latest_battery)
            if self._latest_robot_state:
                snapshot["robot_state"] = dict(self._latest_robot_state)
            return snapshot

    def poll(self) -> list[StatusMessage]:
        """Возвращает накопленные реальные события статуса."""
        with self._lock:
            if not self._queue:
                return []
            out = self._queue[:]
            self._queue.clear()
            return out

