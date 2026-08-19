#!/usr/bin/env bash
set -eo pipefail

ROOT_DIR=/home/unitree/ros2_bridge/bridge_soft
USER_SYSTEMD_DIR="$HOME/.config/systemd/user"

mkdir -p "$USER_SYSTEMD_DIR"
cp -f "$ROOT_DIR/systemd/cmdvel-wireless-bridge.service" "$USER_SYSTEMD_DIR/"
cp -f "$ROOT_DIR/systemd/robot-ws-bridge.service" "$USER_SYSTEMD_DIR/"

systemctl --user daemon-reload
systemctl --user enable --now cmdvel-wireless-bridge.service
systemctl --user enable --now robot-ws-bridge.service

echo "[ok] services enabled and started"
echo "[hint] for autostart after reboot without login: sudo loginctl enable-linger $USER"
