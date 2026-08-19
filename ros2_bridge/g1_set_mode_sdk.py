#!/usr/bin/env python3
import sys

sys.path.insert(0, "/home/unitree/unitree_sdk2_python")

from unitree_sdk2py.core.channel import ChannelFactoryInitialize
from unitree_sdk2py.comm.motion_switcher.motion_switcher_client import MotionSwitcherClient


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "advanced"
    iface = sys.argv[2] if len(sys.argv) > 2 else "eth0"

    ChannelFactoryInitialize(0, iface)

    cli = MotionSwitcherClient()
    cli.SetTimeout(5.0)
    cli.Init()

    ret = cli.SelectMode(mode)
    print("SelectMode(" + mode + ") ret=" + str(ret))


if __name__ == "__main__":
    main()
