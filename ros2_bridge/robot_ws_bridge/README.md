# Robot WS Bridge (ROS2 node) — README для робототехника

## Что это

`Robot WS Bridge` — ROS2 node, который поднимает **WebSocket сервер** на роботе и делает мост:

- **WS → ROS2**: принимает JSON команды и публикует их в ROS2 (MVP: `teleop` → `/cmd_vel`).
- **ROS2 → WS**: отправляет статусы робота клиентам (в MVP **мокируется**, чтобы быстро показать интеграцию).

Архитектурное решение зафиксировано в ADR: `docs/ADR/ADR-0001-robot-ws-ros2-bridge.md`.

## MVP контракт (v1)

### Авторизация

Клиент должен первым сообщением отправить токен:

```json
{"type":"auth","token":"<WS_AUTH_TOKEN>"}
```

### Команда движения (`teleop`)

Сообщение клиента:

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

Маппинг в ROS2 (эквивалент “ручной” команды):

```bash
ros2 topic pub /cmd_vel geometry_msgs/msg/Twist "{linear: {x: 0.57, y: 0.0, z: 0.0}, angular: {x: 0.0, y: 0.0, z: 0.0}}"
```

Т.е. node публикует `geometry_msgs/msg/Twist` в топик `/cmd_vel`.

### Статусы (пока мок)

Клиент может подписаться:

```json
{"type":"subscribe","topics":["robot_state","battery"]}
```

Node будет отправлять `status` сообщения, но источник данных в MVP — **мок**.

## Конфигурация (env)

Минимальный набор переменных окружения (имена можно сохранить такими же в реализации):

- **`WS_AUTH_TOKEN`**: токен авторизации (обязателен)
- **`WS_HOST`**: хост для бинда (например, `0.0.0.0`)
- **`WS_PORT`**: порт (например, `8765`)
- **`CMD_VEL_TOPIC`**: имя топика (по умолчанию `/cmd_vel`)
- **`MOCK_STATUS_TICK_MS`**: период мок-статусов, мс (по умолчанию `500`)

## Как запустить (шаблон)

Ниже приведён **шаблон** шагов запуска. В реализации принят **Python (`rclpy`)** + WS библиотека `websockets` (см. TODO ниже про зависимости).

1) Поднять окружение ROS2 (source):

```bash
source /opt/ros/<distro>/setup.bash
```

2) Собрать workspace (если пакет добавлен в исходники):

```bash
cd <workspace>
colcon build --symlink-install
source install/setup.bash
```

Важно: используйте `source <workspace>/install/setup.bash`.
Не используйте `source src/robot_ws_bridge/install/setup.bash` — это локальные артефакты старой сборки с чужими абсолютными путями.

2) Экспортировать переменные:

```bash
export WS_AUTH_TOKEN="change_me"
export WS_HOST="0.0.0.0"
export WS_PORT="8765"
export CMD_VEL_TOPIC="/cmd_vel"
export MOCK_STATUS_TICK_MS="500"
```

3) Запустить node:

```bash
ros2 run robot_ws_bridge robot_ws_bridge
```

## Как запустить в Docker (рекомендуется на Windows)

Требования:
- Docker Desktop должен быть запущен (Linux containers / WSL2 backend).

Запуск:

```bash
cd robot_ws_bridge
docker compose up --build
```

Проверка, что порт открыт:
- WS будет доступен на `ws://localhost:8765`

## Как протестировать без оркестратора (быстрая проверка)

Для ручной проверки удобно использовать `websocat` (Linux):

```bash
websocat ws://<robot-ip>:8765
```

Далее в открывшемся интерактивном режиме отправьте:

1) Авторизация:

```json
{"type":"auth","token":"change_me"}
```

2) Подписка на статусы (мок):

```json
{"type":"subscribe","topics":["battery","robot_state"]}
```

3) Команда движения:

```json
{"type":"teleop","twist":{"linear":{"x":0.57,"y":0.0,"z":0.0},"angular":{"x":0.0,"y":0.0,"z":0.0}}}
```

## Зависимости (Python)

В окружении, где запускается node, должна быть установлена Python библиотека `websockets`:

```bash
pip install websockets
```

## TODO для подключения реальных статусов (места модификации)

В MVP статусы **мокируются**, чтобы показать WS интеграцию без привязки к конкретным ROS2 сообщениям. Для “боевого” подключения нужно:

- **TODO-1 (battery)**: выбрать источник батареи в ROS2:
  - либо `/battery_state` `sensor_msgs/msg/BatteryState`
  - либо `/diagnostics` `diagnostic_msgs/msg/DiagnosticArray`
  - либо кастомный топик/тип
- **TODO-2 (robot_state)**: определить минимальный список полей состояния (mode, estop, связи, ошибки) и соответствующие ROS2 топики/типы.
- **TODO-3 (частота/дропы)**: определить политику частоты отправки и поведения при медленном клиенте (backpressure).

Технически это будет точка расширения вида:

- модуль/класс `StatusSource` (интерфейс “получить snapshot” + “подписка на изменения”)
- реализация `MockStatusSource` (MVP)
- реализация `RosStatusSource` (подписки на выбранные топики)

## Примечания по интеграции с оркестратором

- **Тик команд** живёт у оркестратора: он отправляет `teleop` с нужной частотой.
- **Тик статусов** живёт на роботе (push) + команда `get_state` (pull) для мгновенного снимка при подключении.

