#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from unitree_api.msg import Request

class SelectModeNode(Node):
    def __init__(self):
        super().__init__("select_mode_normal")
        self.pub = self.create_publisher(Request, "/api/motion_switcher/request", 10)

    def run(self):
        msg = Request()
        msg.header.identity.api_id = 1002  # SelectMode
        msg.parameter = '{"name":"normal"}'
        for _ in range(10):
            self.pub.publish(msg)
            rclpy.spin_once(self, timeout_sec=0.05)
        self.get_logger().info("SelectMode(normal) requests published")


def main():
    rclpy.init()
    node = SelectModeNode()
    node.run()
    node.destroy_node()
    rclpy.shutdown()

if __name__ == "__main__":
    main()
