"""ROS2 node, который связывает WS и ROS2 (/cmd_vel).

В этом модуле сосредоточена ROS2-часть (publisher, spin/shutdown).
WS реализация находится в `ws_server.py`.
"""

from __future__ import annotations

import asyncio
import threading
import time

import rclpy
from geometry_msgs.msg import Twist
from rclpy.node import Node
from sensor_msgs.msg import BatteryState
from std_msgs.msg import String
from unitree_hg.msg import BmsState

from robot_ws_bridge.config import AppConfig
from robot_ws_bridge.status_source import RosStatusSource
from robot_ws_bridge.ws_server import RobotWsServer


class RobotWsBridgeNode(Node):
    """ROS2 node для Robot WS Bridge."""

    def __init__(self, config: AppConfig) -> None:
        """Создаёт node.

        Args:
            config: Конфигурация приложения.
        """
        super().__init__("robot_ws_bridge")
        self._config = config

        self._cmd_vel_pub = self.create_publisher(Twist, config.cmd_vel_topic, 10)
        self.get_logger().info(f"Публикация teleop в топик {config.cmd_vel_topic}")

        self._status_source = RosStatusSource()
        self._battery_sub = self.create_subscription(BatteryState, config.battery_topic, self._on_battery, 10)
        self.get_logger().info(f"Подписка battery на топик {config.battery_topic}")
        self._bms_sub = self.create_subscription(BmsState, "/lf/bmsstate", self._on_bms_state, 10)
        self.get_logger().info("Подписка battery(bms) на топик /lf/bmsstate")
        self._mode_sub = None
        if config.robot_mode_topic:
            self._mode_sub = self.create_subscription(String, config.robot_mode_topic, self._on_mode, 10)
            self.get_logger().info(f"Подписка robot_mode на топик {config.robot_mode_topic}")

        self._ws_server = RobotWsServer(
            host=config.ws_host,
            port=config.ws_port,
            auth_token=config.ws_auth_token,
            status_source=self._status_source,
            teleop_publisher=self.publish_twist,
            status_tick_ms=config.mock_status_tick_ms,
            fsm_state_url=config.fsm_state_url,
        )

        self._ws_thread: threading.Thread | None = None
        self._ws_loop: asyncio.AbstractEventLoop | None = None

    def publish_twist(self, lx: float, ly: float, lz: float, ax: float, ay: float, az: float) -> None:
        """Публикует `geometry_msgs/msg/Twist` в `/cmd_vel`.

        Args:
            lx: linear.x
            ly: linear.y
            lz: linear.z
            ax: angular.x
            ay: angular.y
            az: angular.z
        """
        msg = Twist()
        msg.linear.x = float(lx)
        msg.linear.y = float(ly)
        msg.linear.z = float(lz)
        msg.angular.x = float(ax)
        msg.angular.y = float(ay)
        msg.angular.z = float(az)
        self._cmd_vel_pub.publish(msg)

    def _on_battery(self, msg: BatteryState) -> None:
        level = float(msg.percentage)
        if level > 1.0:
            level = level / 100.0
        level = min(1.0, max(0.0, level))
        self._status_source.update_battery(level=level, ts_ms=int(time.time() * 1000))

    def _on_mode(self, msg: String) -> None:
        self._status_source.update_robot_state(mode=msg.data, ts_ms=int(time.time() * 1000))

    def _on_bms_state(self, msg: BmsState) -> None:
        level = min(1.0, max(0.0, float(msg.soc) / 100.0))
        self._status_source.update_battery(level=level, ts_ms=int(time.time() * 1000))

    def start_ws(self) -> None:
        """Стартует WS сервер в отдельном потоке.

        Причина: `rclpy.spin()` блокирует текущий поток, поэтому WS цикл запускаем
        параллельно.
        """
        if self._ws_thread is not None:
            return

        def runner() -> None:
            loop = asyncio.new_event_loop()
            self._ws_loop = loop
            asyncio.set_event_loop(loop)
            self.get_logger().info(f"WS сервер слушает {self._config.ws_host}:{self._config.ws_port}")
            loop.run_until_complete(self._ws_server.start())
            try:
                loop.run_forever()
            finally:
                loop.run_until_complete(self._ws_server.stop())
                loop.close()

        self._ws_thread = threading.Thread(target=runner, name="robot-ws-bridge-ws", daemon=True)
        self._ws_thread.start()

    def stop_ws(self) -> None:
        """Останавливает WS сервер."""
        if self._ws_loop is not None:
            self._ws_loop.call_soon_threadsafe(self._ws_loop.stop)
        self._ws_thread = None
        self._ws_loop = None


def run_node(config: AppConfig) -> None:
    """Запускает ROS2 node и WS сервер.

    Args:
        config: Конфигурация приложения.
    """
    rclpy.init()
    node = RobotWsBridgeNode(config)
    node.start_ws()
    try:
        rclpy.spin(node)
    finally:
        node.stop_ws()
        node.destroy_node()
        rclpy.shutdown()

