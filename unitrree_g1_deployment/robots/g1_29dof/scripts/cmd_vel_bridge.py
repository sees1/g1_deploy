#!/usr/bin/env python3

import argparse
import json
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

import rclpy
from geometry_msgs.msg import Twist
from rclpy.node import Node


class CmdVelHttpBridge(Node):
    def __init__(self, controller_url: str, topic: str, publish_rate: float, input_timeout: float) -> None:
        super().__init__("g1_cmd_vel_http_bridge")
        self._controller_url = controller_url.rstrip("/")
        self._cmd_vel_endpoint = f"{self._controller_url}/api/cmd_vel"
        self._input_timeout = input_timeout
        self._lock = threading.Lock()
        self._last_command = {"vx": 0.0, "vy": 0.0, "wz": 0.0}
        self._last_rx_time = 0.0
        self._last_error_log_time = 0.0

        self.create_subscription(Twist, topic, self._on_cmd_vel, 10)
        self.create_timer(max(1.0 / publish_rate, 0.01), self._publish_command)
        self.get_logger().info(
            f"Forwarding ROS2 {topic} to {self._cmd_vel_endpoint} at {publish_rate:.1f} Hz"
        )

    def _on_cmd_vel(self, msg: Twist) -> None:
        with self._lock:
            self._last_command = {
                "vx": float(msg.linear.x),
                "vy": float(msg.linear.y),
                "wz": float(msg.angular.z),
            }
            self._last_rx_time = time.monotonic()

    def _current_command(self) -> dict:
        with self._lock:
            age = time.monotonic() - self._last_rx_time
            if self._last_rx_time <= 0.0 or age > self._input_timeout:
                return {"vx": 0.0, "vy": 0.0, "wz": 0.0}
            return dict(self._last_command)

    def _publish_command(self) -> None:
        payload = json.dumps(self._current_command()).encode("utf-8")
        request = urllib.request.Request(
            self._cmd_vel_endpoint,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=0.2) as response:
                response.read()
        except urllib.error.URLError as exc:
            self._log_warning(f"Failed to reach controller API: {exc}")
        except Exception as exc:  # noqa: BLE001
            self._log_warning(f"Failed to forward cmd_vel: {exc}")

    def _log_warning(self, message: str) -> None:
        now = time.monotonic()
        if now - self._last_error_log_time >= 2.0:
            self.get_logger().warn(message)
            self._last_error_log_time = now


def main() -> None:
    parser = argparse.ArgumentParser(description="Forward ROS2 /cmd_vel to g1_29dof HTTP API.")
    parser.add_argument("--controller-url", default="http://127.0.0.1:8080")
    parser.add_argument("--topic", default="/cmd_vel")
    parser.add_argument("--publish-rate", type=float, default=20.0)
    parser.add_argument("--input-timeout", type=float, default=0.5)
    args = parser.parse_args()

    rclpy.init()
    node = CmdVelHttpBridge(
        controller_url=args.controller_url,
        topic=args.topic,
        publish_rate=args.publish_rate,
        input_timeout=args.input_timeout,
    )

    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
