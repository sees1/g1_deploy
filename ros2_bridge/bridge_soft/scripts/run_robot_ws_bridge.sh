#!/usr/bin/env bash
set -eo pipefail

source /home/unitree/ros2_bridge/bridge_soft/config/env_ws_bridge.sh
source /opt/ros/foxy/setup.bash
source /home/unitree/ros2_bridge/robot_ws_bridge/install/setup.bash
source /home/unitree/cyclonedds_ws/install/setup.bash
source /home/unitree/ros2_bridge/unitree_ros2/cyclonedds_ws/install/setup.bash

export ROS_DOMAIN_ID=${ROS_DOMAIN_ID:-0}
export RMW_IMPLEMENTATION=${RMW_IMPLEMENTATION:-rmw_cyclonedds_cpp}
export CYCLONEDDS_URI=${CYCLONEDDS_URI:-file:///home/unitree/cyclonedds_ws/cyclonedds.xml}
unset ROS_LOCALHOST_ONLY

exec ros2 run robot_ws_bridge robot_ws_bridge
