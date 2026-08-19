#!/usr/bin/env python3
import argparse
import asyncio
import json
import os
import subprocess
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Dict
from urllib.parse import urlparse
import websockets


ROBOT_HOST = "unitree@10.18.14.150"
SSH_PASSWORD = "123"
CMD_VEL_PATH = "/home/unitree/unitrree_g1_deployment/robots/g1_29dof/scripts/cmd_vel_bridge.py"
G1_CTRL_PATH = "/home/unitree/unitrree_g1_deployment/robots/g1_29dof/build/g1_ctrl"
DEPLOY_REPO_PATH = "/home/unitree/unitrree_g1_deployment"
CONTROL_MODE = "ssh"
WS_BRIDGE_STATE_URL = "http://127.0.0.1:8765/api/fsm"
WS_BRIDGE_URL = "ws://127.0.0.1:8765"
WS_BRIDGE_ENV_FILE = "/home/unitree/ros2_bridge/robot_ws_bridge/env_ws_bridge.sh"


def _ws_auth_token() -> str:
    token = os.getenv("WS_AUTH_TOKEN")
    if token:
        return token
    try:
        with open(WS_BRIDGE_ENV_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("export WS_AUTH_TOKEN="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    except Exception:
        pass
    return "change_me"


async def _fetch_battery_ws() -> Dict[str, str]:
    token = _ws_auth_token()
    async with websockets.connect(WS_BRIDGE_URL, open_timeout=1.5, close_timeout=1.0) as ws:
        await ws.send(json.dumps({"type": "auth", "token": token}))
        _ = await ws.recv()
        await ws.send(json.dumps({"type": "get_state"}))
        raw = await ws.recv()
        msg = json.loads(raw)
        data = msg.get("data", {})
        battery = data.get("battery", {})
        out = {}
        lvl = battery.get("level")
        if isinstance(lvl, (int, float)):
            out["battery_percent"] = f"{float(lvl) * 100.0:.1f}"
        vol = battery.get("voltage")
        if isinstance(vol, (int, float)):
            out["battery_voltage"] = f"{float(vol):.2f}"
        return out


def _run_remote(command: str) -> subprocess.CompletedProcess:
    if CONTROL_MODE == "local":
        return subprocess.run(["bash", "-lc", command], capture_output=True, text=True, timeout=25)
    cmd = [
        "sshpass",
        "-p",
        SSH_PASSWORD,
        "ssh",
        "-o",
        "StrictHostKeyChecking=no",
        "-o",
        "ConnectTimeout=10",
        ROBOT_HOST,
        command,
    ]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=25)


def start_processes() -> dict:
    remote_cmd = (
        "source /opt/ros/foxy/setup.bash; "
        "source /home/unitree/cyclonedds_ws/install/setup.bash; "
        "source /home/unitree/ros2_bridge/unitree_ros2/cyclonedds_ws/install/setup.bash; "
        "export ROS_DOMAIN_ID=0; "
        "export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp; "
        f"pgrep -x g1_ctrl >/dev/null || nohup {G1_CTRL_PATH} >/tmp/g1_ctrl.log 2>&1 & "
        f"pgrep -f '{CMD_VEL_PATH}' >/dev/null || nohup python3 {CMD_VEL_PATH} "
        "--controller-url http://127.0.0.1:8080 --topic /cmd_vel >/tmp/cmd_vel_bridge.log 2>&1 & "
        "sleep 1; "
        "echo OK"
    )
    result = _run_remote(remote_cmd)
    return {
        "ok": result.returncode == 0,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
    }


def start_g1_ctrl() -> dict:
    remote_cmd = (
        "source /opt/ros/foxy/setup.bash; "
        "source /home/unitree/cyclonedds_ws/install/setup.bash; "
        "source /home/unitree/ros2_bridge/unitree_ros2/cyclonedds_ws/install/setup.bash; "
        "export ROS_DOMAIN_ID=0; "
        "export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp; "
        f"pgrep -x g1_ctrl >/dev/null || nohup {G1_CTRL_PATH} >/tmp/g1_ctrl.log 2>&1 & "
        "sleep 1; "
        "echo OK"
    )
    result = _run_remote(remote_cmd)
    return {
        "ok": result.returncode == 0,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
    }


def start_cmd_vel_bridge() -> dict:
    remote_cmd = (
        "source /opt/ros/foxy/setup.bash; "
        "source /home/unitree/cyclonedds_ws/install/setup.bash; "
        "source /home/unitree/ros2_bridge/unitree_ros2/cyclonedds_ws/install/setup.bash; "
        "export ROS_DOMAIN_ID=0; "
        "export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp; "
        f"nohup python3 {CMD_VEL_PATH} "
        "--controller-url http://127.0.0.1:8080 --topic /cmd_vel >/tmp/cmd_vel_bridge.log 2>&1 & "
        "sleep 1; "
        "echo OK"
    )
    result = _run_remote(remote_cmd)
    return {
        "ok": result.returncode == 0,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
    }


def stop_cmd_vel_bridge() -> dict:
    cmd_vel_path_awk = CMD_VEL_PATH.replace("/", "\\/")
    remote_cmd = (
        f"ps -eo pid,args | awk '$0 ~ /{cmd_vel_path_awk} --controller-url http:\\/\\/127.0.0.1:8080 --topic \\/cmd_vel$/ {{print $1}}' "
        "| xargs -r kill; "
        "sleep 1; "
        "echo OK"
    )
    result = _run_remote(remote_cmd)
    return {
        "ok": result.returncode == 0,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
    }


def stop_g1_ctrl() -> dict:
    remote_cmd = "pgrep -x g1_ctrl | xargs -r kill; sleep 1; echo OK"
    result = _run_remote(remote_cmd)
    return {
        "ok": result.returncode == 0,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
    }


def stop_processes() -> dict:
    remote_cmd = (
        "pgrep -f 'cmd_vel_bridge.py' | xargs -r kill; "
        "pgrep -x g1_ctrl | xargs -r kill; "
        "sleep 1; "
        "echo OK"
    )
    result = _run_remote(remote_cmd)
    return {
        "ok": result.returncode == 0,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
    }


def git_pull_deployment() -> dict:
    remote_cmd = (
        f"cd {DEPLOY_REPO_PATH} && "
        "git pull --ff-only"
    )
    result = _run_remote(remote_cmd)
    return {
        "ok": result.returncode == 0,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
        "path": DEPLOY_REPO_PATH,
    }


def get_status() -> dict:
    cmd_vel_exact = f"python3 {CMD_VEL_PATH} --controller-url http://127.0.0.1:8080 --topic /cmd_vel"
    cmd_vel_path_awk = CMD_VEL_PATH.replace("/", "\\/")
    remote_cmd = (
        f"if ps -eo args | grep -Fx '{cmd_vel_exact}' >/dev/null; then echo cmd_vel_bridge=running; "
        "else echo cmd_vel_bridge=stopped; fi; "
        "if pgrep -x g1_ctrl >/dev/null; then echo g1_ctrl=running; "
        "else echo g1_ctrl=stopped; fi; "
        "ps -C g1_ctrl -o pid= 2>/dev/null | head -n 1 | xargs -I{} echo g1_ctrl_pid={}; "
        f"ps -eo pid,args | awk '/python3 {cmd_vel_path_awk} --controller-url http:\\/\\/127.0.0.1:8080 --topic \\/cmd_vel$/ {{print $1}}' | head -n 1 | "
        "xargs -I{} echo cmd_vel_pid={}"
    )
    result = _run_remote(remote_cmd)
    status = {
        "ok": result.returncode == 0,
        "cmd_vel_bridge": "unknown",
        "g1_ctrl": "unknown",
        "g1_ctrl_pid": "",
        "cmd_vel_pid": "",
        "battery_percent": "unknown",
        "battery_voltage": "unknown",
        "stderr": result.stderr.strip(),
    }
    for line in result.stdout.splitlines():
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        if k in status:
            status[k] = v

    if CONTROL_MODE == "local":
        try:
            batt = asyncio.run(_fetch_battery_ws())
            for k, v in batt.items():
                status[k] = v
        except Exception:
            pass
    else:
        battery_cmd = (
            "timeout 2 curl -sS http://127.0.0.1:8765/api/fsm | "
            "python3 -c \"import json,sys; "
            "d=json.load(sys.stdin); "
            "b=d.get('battery',{}); "
            "lvl=b.get('level'); "
            "vol=b.get('voltage'); "
            "print('battery_percent='+str(round(float(lvl)*100,1)) if isinstance(lvl,(int,float)) else ''); "
            "print('battery_voltage='+str(round(float(vol),2)) if isinstance(vol,(int,float)) else '')\" 2>/dev/null"
        )
        battery_result = _run_remote(battery_cmd)
        for line in battery_result.stdout.splitlines():
            if "=" not in line:
                continue
            k, v = line.split("=", 1)
            if k in status and v:
                status[k] = v
    return status


HTML = """<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Robot Process Control</title>
  <style>
    body { font-family: -apple-system, Segoe UI, sans-serif; margin: 24px; }
    .row { margin: 12px 0; }
    button { margin-right: 10px; padding: 10px 14px; }
    pre { background: #f3f3f3; padding: 12px; border-radius: 8px; white-space: pre-wrap; }
  </style>
</head>
<body>
  <h2>Robot Scripts Control</h2>
  <div class="row">
    <button onclick="callApi('/api/start')">Start (ROS_DOMAIN_ID=0)</button>
    <button onclick="callApi('/api/stop')">Stop</button>
    <button onclick="callApi('/api/start_g1')">Start g1_ctrl</button>
    <button onclick="callApi('/api/stop_g1')">Stop g1_ctrl</button>
    <button onclick="callApi('/api/start_cmd_vel')">Start cmd_vel_bridge</button>
    <button onclick="callApi('/api/stop_cmd_vel')">Stop cmd_vel_bridge</button>
    <button onclick="callApi('/api/pull')">Pull unitrree_g1_deployment</button>
    <button onclick="refreshStatus()">Refresh Status</button>
  </div>
  <pre id="status">Loading...</pre>
  <script>
    async function callApi(path) {
      const r = await fetch(path, {method: 'POST'});
      const j = await r.json();
      await refreshStatus();
      document.getElementById('status').textContent += "\\n\\nAction:\\n" + JSON.stringify(j, null, 2);
    }
    async function refreshStatus() {
      const r = await fetch('/api/status');
      const j = await r.json();
      document.getElementById('status').textContent = JSON.stringify(j, null, 2);
    }
    refreshStatus();
    setInterval(refreshStatus, 5000);
  </script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    def _send_json(self, payload: dict, code: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/":
            body = HTML.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if parsed.path == "/api/status":
            self._send_json(get_status())
            return
        self._send_json({"ok": False, "error": "not found"}, 404)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/start":
            self._send_json(start_processes())
            return
        if parsed.path == "/api/stop":
            self._send_json(stop_processes())
            return
        if parsed.path == "/api/start_g1":
            self._send_json(start_g1_ctrl())
            return
        if parsed.path == "/api/stop_g1":
            self._send_json(stop_g1_ctrl())
            return
        if parsed.path == "/api/start_cmd_vel":
            self._send_json(start_cmd_vel_bridge())
            return
        if parsed.path == "/api/stop_cmd_vel":
            self._send_json(stop_cmd_vel_bridge())
            return
        if parsed.path == "/api/pull":
            self._send_json(git_pull_deployment())
            return
        self._send_json({"ok": False, "error": "not found"}, 404)

    def log_message(self, fmt: str, *args) -> None:
        return


def main() -> None:
    global CONTROL_MODE, ROBOT_HOST, SSH_PASSWORD

    parser = argparse.ArgumentParser(description="Robot web control")
    parser.add_argument("--mode", choices=["local", "ssh"], default="local")
    parser.add_argument("--bind", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8090)
    parser.add_argument("--ssh-host", default=ROBOT_HOST)
    parser.add_argument("--ssh-pass", default=SSH_PASSWORD)
    args = parser.parse_args()

    CONTROL_MODE = args.mode
    ROBOT_HOST = args.ssh_host
    SSH_PASSWORD = args.ssh_pass

    server = ThreadingHTTPServer((args.bind, args.port), Handler)
    print(f"Robot web control started on http://{args.bind}:{args.port} mode={CONTROL_MODE}")
    server.serve_forever()


if __name__ == "__main__":
    main()
