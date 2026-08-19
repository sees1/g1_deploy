# ROS2 маппинг для Robot WS Bridge (MVP)

## WS → ROS2

### `teleop` → publish `/cmd_vel`

- **WS message**: `type=teleop`
- **ROS2 topic**: `/cmd_vel` (настраивается `CMD_VEL_TOPIC`)
- **ROS2 type**: `geometry_msgs/msg/Twist`

Эквивалент ручной команды:

```bash
ros2 topic pub /cmd_vel geometry_msgs/msg/Twist "{linear: {x: 0.57, y: 0.0, z: 0.0}, angular: {x: 0.0, y: 0.0, z: 0.0}}"
```

## ROS2 → WS (MVP: мок)

В MVP статусы берутся из `MockStatusSource`.

### TODO точки расширения

- Подключение батареи:
  - кандидат: `sensor_msgs/msg/BatteryState` из `/battery_state`
  - кандидат: `diagnostic_msgs/msg/DiagnosticArray` из `/diagnostics`
- Подключение robot_state:
  - определить набор ROS2 топиков/типов под вашу платформу.

