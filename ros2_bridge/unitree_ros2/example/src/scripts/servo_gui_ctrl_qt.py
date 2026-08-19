#!/usr/bin/env python3
import struct
import sys
from typing import List

import rclpy
from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import (
    QApplication,
    QComboBox,
    QDoubleSpinBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from rclpy.node import Node
from unitree_go.msg import LowCmd, LowState

POS_STOP_F = 2.146e9
VEL_STOP_F = 16000.0
MOTOR_COUNT = 20
MOTOR_NAMES = [
    "FR_0", "FR_1", "FR_2", "FL_0", "FL_1", "FL_2", "RR_0", "RR_1", "RR_2", "RL_0",
    "RL_1", "RL_2", "M12", "M13", "M14", "M15", "M16", "M17", "M18", "M19",
]


def crc32_core(words: List[int]) -> int:
    crc = 0xFFFFFFFF
    poly = 0x04C11DB7
    for data in words:
        xbit = 1 << 31
        for _ in range(32):
            if crc & 0x80000000:
                crc = ((crc << 1) & 0xFFFFFFFF) ^ poly
            else:
                crc = (crc << 1) & 0xFFFFFFFF
            if data & xbit:
                crc ^= poly
            xbit >>= 1
    return crc & 0xFFFFFFFF


def lowcmd_crc(msg: LowCmd) -> int:
    buf = bytearray()
    buf += struct.pack("<2B", msg.head[0], msg.head[1])
    buf += struct.pack("<2B", msg.level_flag, msg.frame_reserve)
    buf += struct.pack("<2I", msg.sn[0], msg.sn[1])
    buf += struct.pack("<2I", msg.version[0], msg.version[1])
    buf += struct.pack("<H", msg.bandwidth)
    buf += b"\x00\x00"  # align uint16 -> uint32

    for i in range(MOTOR_COUNT):
      m = msg.motor_cmd[i]
      buf += struct.pack("<B", m.mode)
      buf += b"\x00\x00\x00"  # align float fields
      buf += struct.pack("<f", float(m.q))
      buf += struct.pack("<f", float(m.dq))
      buf += struct.pack("<f", float(m.tau))
      buf += struct.pack("<f", float(m.kp))
      buf += struct.pack("<f", float(m.kd))
      buf += struct.pack("<3I", m.reserve[0], m.reserve[1], m.reserve[2])

    buf += struct.pack("<B", msg.bms_cmd.off)
    buf += struct.pack(
        "<3B",
        msg.bms_cmd.reserve[0],
        msg.bms_cmd.reserve[1],
        msg.bms_cmd.reserve[2],
    )
    buf += bytes(msg.wireless_remote)
    buf += bytes(msg.led)
    buf += bytes(msg.fan)
    buf += struct.pack("<B", msg.gpio)
    buf += b"\x00"  # align uint8 -> uint32
    buf += struct.pack("<I", msg.reserve)

    words = list(struct.unpack("<" + "I" * (len(buf) // 4), bytes(buf)))
    return crc32_core(words)


class ServoGuiNode(Node):
    def __init__(self) -> None:
        super().__init__("servo_gui_ctrl_qt")
        self.pub = self.create_publisher(LowCmd, "/lowcmd", 10)
        self.sub = self.create_subscription(LowState, "/lowstate", self._on_lowstate, 10)
        self.low_state = LowState()

        self.cmd = LowCmd()
        self._init_cmd()

    def _init_cmd(self) -> None:
        self.cmd.head[0] = 0xFE
        self.cmd.head[1] = 0xEF
        self.cmd.level_flag = 0xFF
        self.cmd.gpio = 0
        for i in range(MOTOR_COUNT):
            self.cmd.motor_cmd[i].mode = 0x01
            self.cmd.motor_cmd[i].q = POS_STOP_F
            self.cmd.motor_cmd[i].kp = 0.0
            self.cmd.motor_cmd[i].dq = VEL_STOP_F
            self.cmd.motor_cmd[i].kd = 0.0
            self.cmd.motor_cmd[i].tau = 0.0

    def stop_all(self) -> None:
        self._init_cmd()

    def _on_lowstate(self, msg: LowState) -> None:
        self.low_state = msg

    def publish(self) -> None:
        self.cmd.crc = lowcmd_crc(self.cmd)
        self.pub.publish(self.cmd)


class ServoGuiWindow(QMainWindow):
    def __init__(self, node: ServoGuiNode) -> None:
        super().__init__()
        self.node = node
        self.setWindowTitle("Unitree Servo GUI (Qt)")
        self.resize(1150, 780)

        root = QWidget()
        layout = QVBoxLayout(root)

        top = QGroupBox("Edit Command")
        top_grid = QGridLayout(top)

        self.motor_idx = QComboBox()
        for i, name in enumerate(MOTOR_NAMES):
            self.motor_idx.addItem(f"{i}: {name}")

        self.mode = QComboBox()
        self.mode.addItem("0x01 Servo", 0x01)
        self.mode.addItem("0x00 Passive", 0x00)

        self.q = QDoubleSpinBox(); self.q.setRange(-1000.0, 1000.0); self.q.setDecimals(4); self.q.setSingleStep(0.01)
        self.kp = QDoubleSpinBox(); self.kp.setRange(0.0, 1000.0); self.kp.setDecimals(4); self.kp.setSingleStep(0.1)
        self.dq = QDoubleSpinBox(); self.dq.setRange(-500.0, 500.0); self.dq.setDecimals(4); self.dq.setSingleStep(0.01)
        self.kd = QDoubleSpinBox(); self.kd.setRange(0.0, 1000.0); self.kd.setDecimals(4); self.kd.setSingleStep(0.1)
        self.tau = QDoubleSpinBox(); self.tau.setRange(-100.0, 100.0); self.tau.setDecimals(4); self.tau.setSingleStep(0.05)

        apply_btn = QPushButton("Apply To Selected Motor")
        apply_btn.clicked.connect(self.apply_selected_motor)

        stop_btn = QPushButton("STOP ALL")
        stop_btn.clicked.connect(self.stop_all)

        reset_btn = QPushButton("Reset Selected To Stop")
        reset_btn.clicked.connect(self.reset_selected)

        top_grid.addWidget(QLabel("Motor"), 0, 0)
        top_grid.addWidget(self.motor_idx, 0, 1)
        top_grid.addWidget(QLabel("Mode"), 0, 2)
        top_grid.addWidget(self.mode, 0, 3)

        top_grid.addWidget(QLabel("q (rad)"), 1, 0)
        top_grid.addWidget(self.q, 1, 1)
        top_grid.addWidget(QLabel("kp"), 1, 2)
        top_grid.addWidget(self.kp, 1, 3)

        top_grid.addWidget(QLabel("dq (rad/s)"), 2, 0)
        top_grid.addWidget(self.dq, 2, 1)
        top_grid.addWidget(QLabel("kd"), 2, 2)
        top_grid.addWidget(self.kd, 2, 3)

        top_grid.addWidget(QLabel("tau (Nm)"), 3, 0)
        top_grid.addWidget(self.tau, 3, 1)

        btn_row = QHBoxLayout()
        btn_row.addWidget(apply_btn)
        btn_row.addWidget(reset_btn)
        btn_row.addWidget(stop_btn)
        top_grid.addLayout(btn_row, 4, 0, 1, 4)

        self.table = QTableWidget(MOTOR_COUNT, 10)
        self.table.setHorizontalHeaderLabels([
            "Idx", "Name", "Mode", "q_cmd", "q_state", "kp", "dq_cmd", "dq_state", "kd", "tau"
        ])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)

        layout.addWidget(top)
        layout.addWidget(self.table)
        self.setCentralWidget(root)

        self.motor_idx.currentIndexChanged.connect(self.load_selected_motor)
        self.load_selected_motor()

        self.ros_timer = QTimer(self)
        self.ros_timer.timeout.connect(self.on_tick)
        self.ros_timer.start(10)

    def load_selected_motor(self) -> None:
        i = self.motor_idx.currentIndex()
        m = self.node.cmd.motor_cmd[i]
        self.mode.setCurrentIndex(0 if m.mode == 0x01 else 1)
        self.q.setValue(0.0 if m.q == POS_STOP_F else float(m.q))
        self.kp.setValue(float(m.kp))
        self.dq.setValue(0.0 if m.dq == VEL_STOP_F else float(m.dq))
        self.kd.setValue(float(m.kd))
        self.tau.setValue(float(m.tau))

    def apply_selected_motor(self) -> None:
        i = self.motor_idx.currentIndex()
        m = self.node.cmd.motor_cmd[i]
        m.mode = int(self.mode.currentData())
        m.q = float(self.q.value())
        m.kp = float(self.kp.value())
        m.dq = float(self.dq.value())
        m.kd = float(self.kd.value())
        m.tau = float(self.tau.value())

    def reset_selected(self) -> None:
        i = self.motor_idx.currentIndex()
        m = self.node.cmd.motor_cmd[i]
        m.mode = 0x01
        m.q = POS_STOP_F
        m.kp = 0.0
        m.dq = VEL_STOP_F
        m.kd = 0.0
        m.tau = 0.0
        self.load_selected_motor()

    def stop_all(self) -> None:
        self.node.stop_all()
        self.load_selected_motor()

    def on_tick(self) -> None:
        rclpy.spin_once(self.node, timeout_sec=0.0)
        self.node.publish()
        self.refresh_table()

    def refresh_table(self) -> None:
        for i in range(MOTOR_COUNT):
            cmd = self.node.cmd.motor_cmd[i]
            st_q = 0.0
            st_dq = 0.0
            if i < len(self.node.low_state.motor_state):
                st_q = float(self.node.low_state.motor_state[i].q)
                st_dq = float(self.node.low_state.motor_state[i].dq)

            row = [
                str(i),
                MOTOR_NAMES[i],
                f"0x{int(cmd.mode):02X}",
                f"{float(cmd.q):.4f}",
                f"{st_q:.4f}",
                f"{float(cmd.kp):.4f}",
                f"{float(cmd.dq):.4f}",
                f"{st_dq:.4f}",
                f"{float(cmd.kd):.4f}",
                f"{float(cmd.tau):.4f}",
            ]

            for c, text in enumerate(row):
                item = self.table.item(i, c)
                if item is None:
                    item = QTableWidgetItem()
                    self.table.setItem(i, c, item)
                item.setText(text)

    def closeEvent(self, event) -> None:  # noqa: N802
        self.node.stop_all()
        self.node.publish()
        rclpy.shutdown()
        super().closeEvent(event)


def main() -> int:
    rclpy.init(args=None)
    node = ServoGuiNode()
    app = QApplication(sys.argv)
    window = ServoGuiWindow(node)
    window.show()
    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())
