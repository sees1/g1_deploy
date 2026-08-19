#!/usr/bin/env bash
set -eo pipefail

source /opt/ros/foxy/setup.bash
source /home/unitree/cyclonedds_ws/install/setup.bash
source /home/unitree/ros2_bridge/unitree_ros2/cyclonedds_ws/install/setup.bash

export ROS_DOMAIN_ID=${ROS_DOMAIN_ID:-0}
export RMW_IMPLEMENTATION=${RMW_IMPLEMENTATION:-rmw_cyclonedds_cpp}
export CYCLONEDDS_URI=${CYCLONEDDS_URI:-file:///home/unitree/cyclonedds_ws/cyclonedds.xml}
unset ROS_LOCALHOST_ONLY

exec python3 /home/unitree/ros2_bridge/bridge_soft/scripts/cmd_vel_to_wireless_bridge.py
