"""WebSocket сервер Robot WS Bridge.

Реализован минимальный протокол v1:
- auth (обязателен)
- teleop → publish в ROS2 (/cmd_vel)
- subscribe → начать push статусов (источник: мок)
- get_state → snapshot
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import time
from dataclasses import dataclass
from typing import Any, Callable
import requests

from robot_ws_bridge.protocol import ProtocolError, make_ack, make_error, parse_teleop
from robot_ws_bridge.status_source import StatusSource


try:
    import websockets
    from websockets.server import WebSocketServerProtocol
except Exception as exc:  # pragma: no cover
    raise RuntimeError(
        "Не удалось импортировать `websockets`. "
        "Установите зависимость в окружении робота: `pip install websockets`."
    ) from exc


TeleopPublisher = Callable[[float, float, float, float, float, float], None]


@dataclass
class ClientState:
    """Состояние WS клиента."""

    authorized: bool = False
    subscribed_topics: set[str] | None = None


class RobotWsServer:
    """WS сервер, который мостит JSON ↔ ROS2."""

    def __init__(
        self,
        *,
        host: str,
        port: int,
        auth_token: str,
        status_source: StatusSource,
        teleop_publisher: TeleopPublisher,
        status_tick_ms: int = 500,
        fsm_state_url: str = "http://10.18.14.150:8080/api/fsm",
    ) -> None:
        """Создаёт WS сервер.

        Args:
            host: Хост для бинда.
            port: Порт для бинда.
            auth_token: Токен авторизации, ожидаемый от клиента.
            status_source: Источник статусов (в MVP: мок).
            teleop_publisher: Функция публикации Twist в ROS2.
            status_tick_ms: Период отправки статусов (приблизительно).
        """
        self._host = host
        self._port = port
        self._auth_token = auth_token
        self._status_source = status_source
        self._teleop_publisher = teleop_publisher
        self._status_tick_ms = max(50, int(status_tick_ms))
        self._fsm_state_url = fsm_state_url

        self._server: websockets.server.Serve | None = None

    async def start(self) -> None:
        """Запускает WS сервер."""
        self._server = await websockets.serve(self._handler, self._host, self._port, max_size=256 * 1024)

    async def stop(self) -> None:
        """Останавливает WS сервер."""
        if self._server is None:
            return
        self._server.close()
        await self._server.wait_closed()
        self._server = None

    async def _handler(self, websocket: WebSocketServerProtocol) -> None:
        client = ClientState(authorized=False, subscribed_topics=set())

        sender_task = asyncio.create_task(self._status_sender(websocket, client))
        try:
            async for raw in websocket:
                await self._handle_message(websocket, client, raw)
        finally:
            sender_task.cancel()
            with contextlib.suppress(Exception):
                await sender_task

    async def _handle_message(self, websocket: WebSocketServerProtocol, client: ClientState, raw: Any) -> None:
        if not isinstance(raw, str):
            await websocket.send(json.dumps(make_error(ProtocolError("VALIDATION_ERROR", "Сообщение должно быть текстом"))))
            return

        try:
            msg = json.loads(raw)
        except Exception:
            await websocket.send(json.dumps(make_error(ProtocolError("VALIDATION_ERROR", "Некорректный JSON"))))
            return

        if not isinstance(msg, dict):
            await websocket.send(
                json.dumps(make_error(ProtocolError("VALIDATION_ERROR", "JSON сообщение должно быть объектом")))
            )
            return

        msg_type = msg.get("type")
        if not isinstance(msg_type, str):
            await websocket.send(json.dumps(make_error(ProtocolError("VALIDATION_ERROR", "Поле type обязательно"))))
            return

        if msg_type == "auth":
            token = msg.get("token")
            if not isinstance(token, str):
                await websocket.send(
                    json.dumps(make_error(ProtocolError("VALIDATION_ERROR", "Поле token обязательно и должно быть строкой")))
                )
                return
            if token != self._auth_token:
                await websocket.send(json.dumps(make_error(ProtocolError("UNAUTHORIZED", "Неверный токен"))))
                await websocket.close()
                return
            client.authorized = True
            await websocket.send(json.dumps(make_ack(ts=int(time.time() * 1000))))
            return

        if not client.authorized:
            await websocket.send(json.dumps(make_error(ProtocolError("UNAUTHORIZED", "Сначала выполните auth"))))
            return

        if msg_type == "teleop":
            try:
                cmd = parse_teleop(msg)
            except ProtocolError as err:
                await websocket.send(json.dumps(make_error(err)))
                return

            self._teleop_publisher(
                cmd.twist.linear.x,
                cmd.twist.linear.y,
                cmd.twist.linear.z,
                cmd.twist.angular.x,
                cmd.twist.angular.y,
                cmd.twist.angular.z,
            )
            await websocket.send(json.dumps(make_ack(ts=int(time.time() * 1000))))
            return

        if msg_type == "subscribe":
            topics = msg.get("topics")
            if not isinstance(topics, list) or not all(isinstance(t, str) for t in topics):
                await websocket.send(
                    json.dumps(make_error(ProtocolError("VALIDATION_ERROR", "topics должен быть массивом строк")))
                )
                return
            client.subscribed_topics = set(topics)
            await websocket.send(json.dumps(make_ack(ts=int(time.time() * 1000))))
            return

        if msg_type == "get_state":
            try:
                snapshot = self._status_source.get_snapshot()
                loop = asyncio.get_running_loop()
                current_state = await loop.run_in_executor(None, self._fetch_fsm_current_state)
                snapshot["fsm"] = {"current_state": current_state}
            except requests.RequestException as err:
                snapshot = self._status_source.get_snapshot()
                snapshot["fsm_error"] = f"HTTP error: {err}"
            except ValueError:
                snapshot = self._status_source.get_snapshot()
                snapshot["fsm_error"] = "Response is not valid JSON"
            except Exception as err:
                snapshot = self._status_source.get_snapshot()
                snapshot["fsm_error"] = f"Unexpected error: {type(err).__name__}: {err}"
            payload = {"type": "state_snapshot", "ts": int(time.time() * 1000), "data": snapshot}
            await websocket.send(json.dumps(payload))
            return

        await websocket.send(json.dumps(make_error(ProtocolError("VALIDATION_ERROR", f"Неизвестный type={msg_type}"))))

    async def _status_sender(self, websocket: WebSocketServerProtocol, client: ClientState) -> None:
        """Периодически отправляет статусы подписанным клиентам."""
        while True:
            await asyncio.sleep(self._status_tick_ms / 1000.0)
            if not client.authorized:
                continue

            subscribed = client.subscribed_topics or set()
            if not subscribed:
                continue

            for msg in self._status_source.poll():
                if msg.topic not in subscribed:
                    continue
                payload = {"type": "status", "topic": msg.topic, "ts": msg.ts, "data": msg.data}
                try:
                    await websocket.send(json.dumps(payload))
                except Exception:
                    return

    def _fetch_fsm_current_state(self) -> Any:
        response = requests.get(self._fsm_state_url, timeout=2)
        response.raise_for_status()
        data = response.json()
        return data.get("current_state")

