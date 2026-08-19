#!/usr/bin/env python3
import math

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, QoSReliabilityPolicy, QoSDurabilityPolicy

from geometry_msgs.msg import Twist
from unitree_go.msg import WirelessController


class CmdVelToWirelessBridge(Node):
    def __init__(self):
        super().__init__("cmd_vel_to_wireless_bridge")

        # Max physical velocities used for normalization to joystick [-1..1]
        self.max_vx = float(self.declare_parameter("max_vx", 0.5).value)
        self.max_wz = float(self.declare_parameter("max_wz", 0.8).value)

        # Signs for mapping (G1 usually uses ly<0 for forward)
        self.ly_sign = float(self.declare_parameter("ly_sign", 1.0).value)
        self.rx_sign = float(self.declare_parameter("rx_sign", -1.0).value)

        self.cmd_timeout_sec = float(self.declare_parameter("cmd_timeout_sec", 0.35).value)

        qos = QoSProfile(depth=10)
        qos.reliability = QoSReliabilityPolicy.RELIABLE
        qos.durability = QoSDurabilityPolicy.VOLATILE

        self.pub = self.create_publisher(WirelessController, "/wirelesscontroller", qos)
        self.sub = self.create_subscription(Twist, "/cmd_vel", self.on_cmd_vel, 20)
        self.timer = self.create_timer(0.1, self.on_timer)

        self.last_cmd_time = None
        self.sent_zero = False

        self.get_logger().info("Started bridge: /cmd_vel -> /wirelesscontroller")

    @staticmethod
    def clamp(v: float, lo: float = -1.0, hi: float = 1.0) -> float:
        return max(lo, min(hi, v))

    def publish_wireless(self, lx: float, ly: float, rx: float, ry: float, keys: int = 0):
        msg = WirelessController()
        msg.lx = float(self.clamp(lx))
        msg.ly = float(self.clamp(ly))
        msg.rx = float(self.clamp(rx))
        msg.ry = float(self.clamp(ry))
        msg.keys = int(keys) & 0xFFFF
        self.pub.publish(msg)

    def on_cmd_vel(self, msg: Twist):
        # linear.x -> ly, angular.z -> rx
        ly = self.ly_sign * (float(msg.linear.x) / self.max_vx if self.max_vx > 1e-6 else 0.0)
        rx = self.rx_sign * (float(msg.angular.z) / self.max_wz if self.max_wz > 1e-6 else 0.0)

        self.publish_wireless(0.0, ly, rx, 0.0, 0)
        self.last_cmd_time = self.get_clock().now()
        self.sent_zero = False

        self.get_logger().info(f"WIRELESS sent: ly={ly:.3f} rx={rx:.3f}")

    def on_timer(self):
        if self.last_cmd_time is None:
            return
        dt = (self.get_clock().now() - self.last_cmd_time).nanoseconds / 1e9
        if dt > self.cmd_timeout_sec and not self.sent_zero:
            self.publish_wireless(0.0, 0.0, 0.0, 0.0, 0)
            self.sent_zero = True
            self.get_logger().warn("cmd_vel timeout -> sent zero wireless sticks")


def main():
    rclpy.init()
    node = CmdVelToWirelessBridge()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
