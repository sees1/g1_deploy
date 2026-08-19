#!/usr/bin/env python3
import os
import subprocess
import time

MODES = ["normal", "ai", "advanced"]
ENV = os.environ.copy()


def run(cmd, timeout=8):
    try:
        p = subprocess.run(cmd, shell=True, text=True, capture_output=True, timeout=timeout, env=ENV)
        return p.returncode, p.stdout.strip(), p.stderr.strip()
    except subprocess.TimeoutExpired:
        return 124, "", "timeout"


def publish_select(mode):
    code = (
        "import rclpy\n"
        "from rclpy.node import Node\n"
        "from unitree_api.msg import Request\n"
        "rclpy.init()\n"
        "node=Node(\"select_mode_once\")\n"
        "pub=node.create_publisher(Request,\"/api/motion_switcher/request\",10)\n"
        f"msg=Request(); msg.header.identity.api_id=1002; msg.parameter=\"{{\\\"name\\\":\\\"{mode}\\\"}}\"\n"
        "\n"
        "for _ in range(10):\n"
        "    pub.publish(msg)\n"
        "    rclpy.spin_once(node,timeout_sec=0.05)\n"
        "print(\"sent\")\n"
        "node.destroy_node()\n"
        "rclpy.shutdown()\n"
    )
    cmd = "python3 - <<EOF\n" + code + "EOF"
    return run(cmd, timeout=12)


def sport_status():
    _, out, _ = run("ros2 topic info /api/sport/request", timeout=6)
    sub = -1
    for line in out.splitlines():
        if "Subscription count:" in line:
            try:
                sub = int(line.split(":")[-1].strip())
            except Exception:
                pass
    return sub, out


def fsm_status():
    cmd = "timeout 6 /home/unitree/ros2_bridge/unitree_ros2/example/install/unitree_ros2_example/bin/g1_loco_client_example --get_fsm_id"
    _, out, _ = run(cmd, timeout=10)
    ok = "current fsm_id:" in out
    return ok, out


for mode in MODES:
    print(f"=== TRY MODE: {mode} ===")
    rc, out, err = publish_select(mode)
    print(f"select rc={rc} out={out} err={err}")
    time.sleep(1.5)
    sub, _ = sport_status()
    print(f"sport_subscribers={sub}")
    ok, fout = fsm_status()
    print(f"fsm_ok={ok}")
    if fout:
        print(fout)

print("DONE")
