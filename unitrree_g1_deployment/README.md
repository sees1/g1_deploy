# Build Flags

This repository supports selecting the ONNX Runtime package at CMake configure time for:

- `robots/g1_29dof`
- `robots/a1_23dof`

## Supported Flag

- `USE_ONNXRUNTIME_AARCH64`
  - `OFF` by default
  - When `OFF`, the build uses `thirdparty/onnxruntime-linux-x64-1.22.0`
  - When `ON`, the build uses `thirdparty/onnxruntime-linux-aarch64-1.23.2`

## Build Examples

### x64 build

```bash
cd robots/g1_29dof/build
cmake ..
make
```

```bash
cd robots/a1_23dof/build
cmake ..
make
```

### aarch64 build

```bash
cd robots/g1_29dof/build
cmake .. -DUSE_ONNXRUNTIME_AARCH64=ON
make
```

```bash
cd robots/a1_23dof/build
cmake .. -DUSE_ONNXRUNTIME_AARCH64=ON
make
```

## Deployment Usage

Ниже приведён базовый порядок запуска деплоя контроллера и подачи команд скорости.

### G1 29DoF

1. Соберите проект:

```bash
cd robots/g1_29dof/build
cmake ..
make
```

2. Запустите контроллер:

```bash
cd robots/g1_29dof/build
./g1_ctrl
```

3. Переведите робота в рабочие состояния с пульта:
   - `L2 + Up` для перехода в `FixStand`
   - `R1 + X` для перехода в `Velocity`

4. Перед запуском ROS2-узлов установите `ROS_DOMAIN_ID=0`:

```bash
export ROS_DOMAIN_ID=0
```

5. Запустите ROS2 bridge для трансляции сообщений `geometry_msgs/Twist` из топика `/cmd_vel` в HTTP API контроллера:

```bash
python3 robots/g1_29dof/scripts/cmd_vel_bridge.py --controller-url http://127.0.0.1:8080 --topic /cmd_vel
```

Важно: bridge нужно запускать обязательно, если вы хотите управлять роботом через ROS2-топик `/cmd_vel`. Без него сообщения из ROS2 не будут отправляться в контроллер.

По умолчанию bridge пересылает команды в `POST /api/cmd_vel`, а сам контроллер поднимает API на порту `8080` из `robots/g1_29dof/config/config.yaml`.

Состояние контроллера также можно переключать по HTTP. Например, чтобы перевести FSM в `Passive`, можно отправить `POST` запрос на `http://127.0.0.1:8080/api/fsm/transition` с JSON payload:

```python
import requests

URL = "http://127.0.0.1:8080/api/fsm/transition"

payload = {
    "state": "Passive"
}

headers = {
    "Content-Type": "application/json"
}

response = requests.post(URL, json=payload, headers=headers)

print(response.status_code)
print(response.text)
```

### A1 23DoF

1. Соберите проект:

```bash
cd robots/a1_23dof/build
cmake ..
make
```

2. Запустите контроллер:

```bash
cd robots/a1_23dof/build
./a1_ctrl
```

3. Переведите робота в рабочие состояния с пульта:
   - `L2 + Up` для перехода в `FixStand`
   - `R1 + X` для перехода в `Velocity`

4. Перед запуском ROS2-узлов установите `ROS_DOMAIN_ID=0`:

```bash
export ROS_DOMAIN_ID=0
```

5. Запустите bridge для трансляции ROS2 `/cmd_vel` в контроллер:

```bash
python3 robots/a1_23dof/scripts/cmd_vel_bridge.py --controller-url http://127.0.0.1:8080 --topic /cmd_vel
```

Важно: для управления через ROS2 также необходимо запускать bridge, иначе команды скорости не попадут в HTTP API контроллера.

Для `A1` переключение состояния по HTTP выполняется аналогично, через `POST http://127.0.0.1:8080/api/fsm/transition` с JSON вида `{"state": "Passive"}`.
