"""Точка входа для `ros2 run robot_ws_bridge robot_ws_bridge`.

Важно: исполняемый файл появляется после `colcon build` из `console_scripts`
в `setup.py`. В исходниках “бинарника” вы не увидите — это нормально для
Python ROS2 пакетов.
"""

from __future__ import annotations

import sys

from robot_ws_bridge.config import load_config
from robot_ws_bridge.ros_bridge_node import run_node


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint.

    Args:
        argv: Аргументы командной строки.

    Returns:
        Код возврата процесса.
    """
    _ = argv or sys.argv
    try:
        config = load_config()
    except Exception as exc:
        print(f"Ошибка конфигурации: {exc}", file=sys.stderr)
        return 2

    run_node(config)
    return 0

