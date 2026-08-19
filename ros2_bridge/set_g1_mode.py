#!/usr/bin/env python3
import json
import sys
import time

import rclpy
from rclpy.node import Node
from unitree_api.msg import Request

class ModePublisher(Node):
    def __init__(self):
        super().__init__("set_g1_mode_pub")
        self.pub = self.create_publisher(Request, "/api/motion_switcher/request", 10)

    def send(self, mode: str):
        msg = Request()
        msg.header.identity.api_id = 1002  # SelectMode
        msg.parameter = json.dumps({"name": mode})
        for _ in range(10):
            self.pub.publish(msg)
            rclpy.spin_once(self, timeout_sec=0.05)
        self.get_logger().info("SelectMode published: " + mode)


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "sport"
    rclpy.init()
    n = ModePublisher()
    n.send(mode)
    n.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
