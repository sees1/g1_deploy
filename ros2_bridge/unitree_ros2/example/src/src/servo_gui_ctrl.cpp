#include <algorithm>
#include <array>
#include <chrono>
#include <cstdio>
#include <string>

#include <ncurses.h>

#include "common/motor_crc.h"
#include "rclcpp/rclcpp.hpp"
#include "unitree_go/msg/low_cmd.hpp"
#include "unitree_go/msg/low_state.hpp"

namespace {
constexpr int kMotorCount = 20;

const std::array<const char*, kMotorCount> kMotorNames = {
    "FR_0", "FR_1", "FR_2", "FL_0", "FL_1", "FL_2", "RR_0", "RR_1", "RR_2", "RL_0",
    "RL_1", "RL_2", "M12",  "M13",  "M14",  "M15",  "M16",  "M17",  "M18", "M19"};

const std::array<const char*, 6> kFieldNames = {"q", "kp", "dq", "kd", "tau", "mode"};
}

class ServoGuiCtrlNode : public rclcpp::Node {
 public:
  ServoGuiCtrlNode() : Node("servo_gui_ctrl") {
    cmd_pub_ = this->create_publisher<unitree_go::msg::LowCmd>("/lowcmd", 10);
    low_state_sub_ = this->create_subscription<unitree_go::msg::LowState>(
        "/lowstate", 10,
        [this](const unitree_go::msg::LowState::SharedPtr msg) { low_state_ = *msg; });

    InitLowCmd();
    InitUi();

    timer_ = this->create_wall_timer(std::chrono::milliseconds(5), [this] {
      HandleInput();
      Publish();
      DrawUi();
    });
  }

  ~ServoGuiCtrlNode() override {
    if (ui_ready_) {
      endwin();
    }
  }

 private:
  void InitLowCmd() {
    cmd_msg_.head[0] = 0xFE;
    cmd_msg_.head[1] = 0xEF;
    cmd_msg_.level_flag = 0xFF;
    cmd_msg_.gpio = 0;

    for (int i = 0; i < kMotorCount; ++i) {
      cmd_msg_.motor_cmd[i].mode = 0x01;
      cmd_msg_.motor_cmd[i].q = PosStopF;
      cmd_msg_.motor_cmd[i].kp = 0.0F;
      cmd_msg_.motor_cmd[i].dq = VelStopF;
      cmd_msg_.motor_cmd[i].kd = 0.0F;
      cmd_msg_.motor_cmd[i].tau = 0.0F;
    }
  }

  void InitUi() {
    initscr();
    cbreak();
    noecho();
    keypad(stdscr, TRUE);
    nodelay(stdscr, TRUE);
    curs_set(0);
    timeout(0);
    ui_ready_ = true;
  }

  void SafeStopAll() {
    for (int i = 0; i < kMotorCount; ++i) {
      cmd_msg_.motor_cmd[i].q = PosStopF;
      cmd_msg_.motor_cmd[i].kp = 0.0F;
      cmd_msg_.motor_cmd[i].dq = VelStopF;
      cmd_msg_.motor_cmd[i].kd = 0.0F;
      cmd_msg_.motor_cmd[i].tau = 0.0F;
      cmd_msg_.motor_cmd[i].mode = 0x01;
    }
  }

  void HandleInput() {
    const int ch = getch();
    if (ch == ERR) {
      return;
    }

    switch (ch) {
      case 'q':
      case 'Q':
        SafeStopAll();
        Publish();
        rclcpp::shutdown();
        return;
      case KEY_UP:
        selected_motor_ = std::max(0, selected_motor_ - 1);
        return;
      case KEY_DOWN:
        selected_motor_ = std::min(kMotorCount - 1, selected_motor_ + 1);
        return;
      case KEY_LEFT:
        selected_field_ = (selected_field_ + static_cast<int>(kFieldNames.size()) - 1) %
                          static_cast<int>(kFieldNames.size());
        return;
      case KEY_RIGHT:
        selected_field_ = (selected_field_ + 1) % static_cast<int>(kFieldNames.size());
        return;
      case 's':
      case 'S':
        SafeStopAll();
        return;
      case 'r':
      case 'R':
        InitLowCmd();
        return;
      case '+':
      case '=':
        ApplyDelta(step_);
        return;
      case '-':
      case '_':
        ApplyDelta(-step_);
        return;
      case ']':
        step_ = std::min(step_ * 2.0F, 5.0F);
        return;
      case '[':
        step_ = std::max(step_ / 2.0F, 0.001F);
        return;
      default:
        return;
    }
  }

  void ApplyDelta(float delta) {
    auto &m = cmd_msg_.motor_cmd[selected_motor_];
    switch (selected_field_) {
      case 0:
        if (m.q == PosStopF) {
          m.q = 0.0F;
        }
        m.q += delta;
        break;
      case 1:
        m.kp = std::max(0.0F, m.kp + delta);
        break;
      case 2:
        if (m.dq == VelStopF) {
          m.dq = 0.0F;
        }
        m.dq += delta;
        break;
      case 3:
        m.kd = std::max(0.0F, m.kd + delta);
        break;
      case 4:
        m.tau += delta;
        break;
      case 5:
        if (delta > 0) {
          m.mode = (m.mode == 0x01) ? 0x00 : 0x01;
        } else {
          m.mode = (m.mode == 0x01) ? 0x00 : 0x01;
        }
        break;
      default:
        break;
    }
  }

  void DrawUi() {
    erase();

    mvprintw(0, 0, "Unitree Servo GUI (low-level /lowcmd)  |  q:exit  s:stop all  r:reset  +/-:change  [/]:step");
    mvprintw(1, 0, "Selected motor: %d (%s) | Selected field: %s | step=%.4f", selected_motor_,
             kMotorNames[selected_motor_], kFieldNames[selected_field_], step_);

    mvprintw(3, 0, "Idx Name   mode      q(cmd)    q(state)      kp        dq(cmd)    dq(state)      kd        tau");

    for (int i = 0; i < kMotorCount; ++i) {
      const auto &cmd = cmd_msg_.motor_cmd[i];
      const bool have_state = i < static_cast<int>(low_state_.motor_state.size());
      const float q_state = have_state ? low_state_.motor_state[i].q : 0.0F;
      const float dq_state = have_state ? low_state_.motor_state[i].dq : 0.0F;

      if (i == selected_motor_) {
        attron(A_REVERSE);
      }

      mvprintw(4 + i, 0,
               "%2d  %-4s  0x%02X  %10.4f  %10.4f  %8.3f  %10.4f  %10.4f  %8.3f  %8.3f",
               i, kMotorNames[i], static_cast<unsigned int>(cmd.mode), cmd.q, q_state, cmd.kp, cmd.dq,
               dq_state, cmd.kd, cmd.tau);

      if (i == selected_motor_) {
        attroff(A_REVERSE);
      }
    }

    mvprintw(26, 0,
             "Keys: UP/DOWN motor | LEFT/RIGHT field | +/- edit | '[' halve step | ']' double step | 's' STOP");

    refresh();
  }

  void Publish() {
    get_crc(cmd_msg_);
    cmd_pub_->publish(cmd_msg_);
  }

  rclcpp::Publisher<unitree_go::msg::LowCmd>::SharedPtr cmd_pub_;
  rclcpp::Subscription<unitree_go::msg::LowState>::SharedPtr low_state_sub_;
  rclcpp::TimerBase::SharedPtr timer_;

  unitree_go::msg::LowCmd cmd_msg_;
  unitree_go::msg::LowState low_state_;

  int selected_motor_ = 0;
  int selected_field_ = 0;
  float step_ = 0.02F;
  bool ui_ready_ = false;
};

int main(int argc, char **argv) {
  rclcpp::init(argc, argv);
  auto node = std::make_shared<ServoGuiCtrlNode>();
  rclcpp::spin(node);
  rclcpp::shutdown();
  return 0;
}
