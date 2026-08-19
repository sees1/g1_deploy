#!/usr/bin/env bash
set -eo pipefail

source /opt/ros/foxy/setup.bash
source /home/unitree/cyclonedds_ws/install/setup.bash
source /home/unitree/ros2_bridge/unitree_ros2/cyclonedds_ws/install/setup.bash
source /home/unitree/ros2_bridge/unitree_ros2/example/install/setup.bash

export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
export ROS_DOMAIN_ID=${ROS_DOMAIN_ID:-1}
export CYCLONEDDS_URI=file:///home/unitree/cyclonedds_ws/cyclonedds.xml
unset ROS_LOCALHOST_ONLY

exec /home/unitree/ros2_bridge/unitree_ros2/example/install/unitree_ros2_example/bin/ros2_bridge \
  --ros-args \
  -p max_vx:=0.5 \
  -p max_vy:=0.3 \
  -p max_wz:=0.8 \
  -p cmd_timeout_sec:=0.35
