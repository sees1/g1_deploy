import sys
if sys.prefix == '/usr':
    sys.real_prefix = sys.prefix
    sys.prefix = sys.exec_prefix = '/home/unitree/ros2_bridge/robot_ws_bridge/install/robot_ws_bridge'
