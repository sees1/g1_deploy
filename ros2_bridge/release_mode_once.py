#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from unitree_api.msg import Request

class ReleaseModeNode(Node):
    def __init__(self):
        super().__init__("release_mode_once")
        self.pub = self.create_publisher(Request, "/api/motion_switcher/request", 10)

    def run(self):
        msg = Request()
        msg.header.identity.api_id = 1003
        msg.header.lease.id = 0
        msg.header.policy.priority = 0
        msg.header.policy.noreply = False
        msg.parameter = ""
        msg.binary = []

        for _ in range(10):
            self.pub.publish(msg)
            rclpy.spin_once(self, timeout_sec=0.05)

        self.get_logger().info("ReleaseMode requests published")


def main():
    rclpy.init()
    node = ReleaseModeNode()
    node.run()
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
