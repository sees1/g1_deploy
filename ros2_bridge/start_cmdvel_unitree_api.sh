#!/usr/bin/env bash
set -eo pipefail

source /opt/ros/foxy/setup.bash
source /home/unitree/cyclonedds_ws/install/setup.bash
source /home/unitree/ros2_bridge/unitree_ros2/cyclonedds_ws/install/setup.bash
source /home/unitree/ros2_bridge/unitree_ros2/example/install/setup.bash

export ROS_DOMAIN_ID=${ROS_DOMAIN_ID:-0}
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
export CYCLONEDDS_URI=file:///home/unitree/cyclonedds_ws/cyclonedds.xml
unset ROS_LOCALHOST_ONLY

LOCO_BIN=/home/unitree/ros2_bridge/unitree_ros2/example/install/unitree_ros2_example/bin/g1_loco_client_example

get_fsm_id() {
  local out
  out=$(timeout 6 "$LOCO_BIN" --get_fsm_id 2>&1 || true)
  echo "$out" | sed -n "s/.*current fsm_id: \([0-9][0-9]*\).*/\1/p" | tail -n1
}

sport_subscribers() {
  ros2 topic info /api/sport/request | grep -F "Subscription count:" | cut -d: -f2 | tr -d " " || true
}

ensure_backend() {
  local i sub
  for i in $(seq 1 20); do
    sub=$(sport_subscribers)
    if [ -n "$sub" ] && [ "$sub" -ge 1 ] 2>/dev/null; then
      echo "[backend] /api/sport/request subscribers=$sub"
      return 0
    fi
    echo "[backend] waiting /api/sport/request subscriber... ($i/20)"
    sleep 0.5
  done
  return 1
}

ensure_loco_ready() {
  local attempt mode fsm

  # Attempt sequence: set mode -> stand_up -> start -> check fsm
  for attempt in $(seq 1 4); do
    echo "[loco] attempt $attempt"
    for mode in "${1:-sport}" normal advanced; do
      echo "[mode] trying: $mode"
      python3 /home/unitree/ros2_bridge/set_g1_mode.py "$mode" || true
      sleep 0.7
    done

    # Try to activate locomotion fsm path
    timeout 6 "$LOCO_BIN" --stand_up >/dev/null 2>&1 || true
    sleep 0.5
    timeout 6 "$LOCO_BIN" --start >/dev/null 2>&1 || true
    sleep 0.7

    fsm=$(get_fsm_id)
    echo "[loco] fsm_id=${fsm:-unknown}"

    # 801 means motion owner still holds control; 0/1/4 are non-walk states.
    if [ -n "$fsm" ] && [ "$fsm" != "801" ] && [ "$fsm" != "0" ] && [ "$fsm" != "1" ] && [ "$fsm" != "4" ]; then
      echo "[loco] locomotion accepted (fsm_id=$fsm)"
      return 0
    fi
  done

  return 1
}

if ! ensure_backend; then
  echo "[error] sport backend not active; cmd_vel bridge not started"
  exit 2
fi

if ! ensure_loco_ready "${1:-sport}"; then
  echo "[error] robot still not in executable locomotion state (fsm likely 801/0/1/4)"
  echo "[hint] switch robot to SPORT/WALK mode from joystick, then rerun"
  exit 3
fi

exec /home/unitree/ros2_bridge/unitree_ros2/example/install/unitree_ros2_example/bin/ros2_bridge \
  --ros-args \
  -p max_vx:=0.5 \
  -p max_vy:=0.3 \
  -p max_wz:=0.8 \
  -p cmd_timeout_sec:=0.35
