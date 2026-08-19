# bridge_soft

Переносимый набор для G1 с двумя сервисами:
1. `cmdvel-wireless-bridge.service` (`/cmd_vel -> /wirelesscontroller`)
2. `robot-ws-bridge.service` (WebSocket -> `/cmd_vel`)

## Установка
```bash
cd /home/unitree/ros2_bridge/bridge_soft
./install.sh
```

## Проверка
```bash
systemctl --user status cmdvel-wireless-bridge.service
systemctl --user status robot-ws-bridge.service
```

## Логи
```bash
journalctl --user -u cmdvel-wireless-bridge.service -f
journalctl --user -u robot-ws-bridge.service -f
```

## Автостарт после ребута без логина
```bash
sudo loginctl enable-linger unitree
```
