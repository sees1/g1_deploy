# Протокол Robot WS Bridge — v1

## Общие принципы

- Транспорт: WebSocket (`ws://`).
- Формат: JSON.
- Все сообщения MUST содержать поле `type` (строка).
- До выполнения любых команд клиент MUST пройти авторизацию (`type=auth`).
- Сервер отвечает структурированными сообщениями `ack` или `error`.

## Авторизация

### `auth` (client → server)

```json
{"type":"auth","token":"<WS_AUTH_TOKEN>"}
```

Правила:
- Токен сравнивается с `WS_AUTH_TOKEN` из окружения.
- IF токен неверен THEN сервер возвращает `error` и закрывает соединение.

## Команды

### `teleop` (client → server)

Назначение: публиковать `geometry_msgs/msg/Twist` в топик `/cmd_vel` (или `CMD_VEL_TOPIC`).

```json
{
  "type": "teleop",
  "ts": 1234567890,
  "twist": {
    "linear":  { "x": 0.57, "y": 0.0, "z": 0.0 },
    "angular": { "x": 0.0,  "y": 0.0, "z": 0.0 }
  }
}
```

Валидация:
- `twist.linear.*` и `twist.angular.*` MUST быть числами.
- Поля могут отсутствовать; тогда трактуются как 0.0 (решение реализации).

Ответ:
- `ack` (server → client) — команда принята к исполнению/публикации.

## Подписки и статусы

### `subscribe` (client → server)

```json
{"type":"subscribe","topics":["robot_state","battery"]}
```

Примечание: в MVP статусы могут быть мок-данными.

### `status` (server → client)

```json
{
  "type": "status",
  "topic": "battery",
  "ts": 1234567890,
  "data": { "level": 0.87 }
}
```

### `get_state` (client → server)

```json
{"type":"get_state"}
```

### `state_snapshot` (server → client)

```json
{
  "type": "state_snapshot",
  "ts": 1234567890,
  "data": {
    "battery": { "level": 0.87 },
    "robot_state": { "mode": "manual" }
  }
}
```

## Служебные ответы

### `ack` (server → client)

```json
{"type":"ack","requestId":"optional","ts":1234567890}
```

### `error` (server → client)

```json
{
  "type": "error",
  "code": "VALIDATION_ERROR",
  "message": "Человекочитаемое описание",
  "details": {}
}
```

Рекомендуемые коды:
- `UNAUTHORIZED`
- `VALIDATION_ERROR`
- `ROS_NOT_READY`
- `INTERNAL_ERROR`

