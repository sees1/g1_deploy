#include <algorithm>
#include <chrono>
#include <cstdint>
#include <string>

#include "geometry_msgs/msg/twist.hpp"
#include "nlohmann/json.hpp"
#include "rclcpp/rclcpp.hpp"
#include "unitree_api/msg/request.hpp"

namespace {
constexpr int32_t ROBOT_SPORT_API_ID_MOVE = 1008;
constexpr int32_t ROBOT_SPORT_API_ID_STOPMOVE = 1003;
}

class CmdVelToUnitreeBridge : public rclcpp::Node {
 public:
  CmdVelToUnitreeBridge()
      : Node("cmd_vel_to_unitree_bridge"),
        max_vx_(declare_parameter<double>("max_vx", 0.5)),
        max_vy_(declare_parameter<double>("max_vy", 0.3)),
        max_wz_(declare_parameter<double>("max_wz", 0.8)),
        cmd_timeout_sec_(declare_parameter<double>("cmd_timeout_sec", 0.35)) {
    req_pub_ = create_publisher<unitree_api::msg::Request>("/api/sport/request", 10);

    cmd_vel_sub_ = create_subscription<geometry_msgs::msg::Twist>(
        "/cmd_vel", 20,
        std::bind(&CmdVelToUnitreeBridge::on_cmd_vel, this, std::placeholders::_1));

    watchdog_timer_ = create_wall_timer(
        std::chrono::milliseconds(100),
        std::bind(&CmdVelToUnitreeBridge::on_watchdog, this));

    RCLCPP_INFO(get_logger(),
                "Started cmd_vel bridge: /cmd_vel -> /api/sport/request (MOVE api_id=%d)",
                ROBOT_SPORT_API_ID_MOVE);
  }

 private:
  static double clamp(double value, double abs_limit) {
    return std::max(-abs_limit, std::min(value, abs_limit));
  }

  void fill_request(unitree_api::msg::Request &req, int32_t api_id,
                    const std::string &parameter = "") {
    req.header.identity.api_id = api_id;
    req.header.identity.id =
        static_cast<uint64_t>(this->get_clock()->now().nanoseconds());
    req.parameter = parameter;
  }

  void publish_move(double vx, double vy, double wz) {
    nlohmann::json js;
    js["x"] = vx;
    js["y"] = vy;
    js["z"] = wz;

    unitree_api::msg::Request req;
    fill_request(req, ROBOT_SPORT_API_ID_MOVE, js.dump());
    req_pub_->publish(req);
    RCLCPP_INFO(this->get_logger(), "MOVE sent: x=%.3f y=%.3f z=%.3f", vx, vy, wz);
  }

  void publish_stop() {
    unitree_api::msg::Request req;
    fill_request(req, ROBOT_SPORT_API_ID_STOPMOVE);
    req_pub_->publish(req);
    RCLCPP_INFO(this->get_logger(), "STOP sent");
  }

  void on_cmd_vel(const geometry_msgs::msg::Twist::SharedPtr msg) {
    const double vx = clamp(msg->linear.x, max_vx_);
    const double vy = clamp(msg->linear.y, max_vy_);
    const double wz = clamp(msg->angular.z, max_wz_);

    publish_move(vx, vy, wz);
    last_cmd_time_ = now();
    sent_stop_after_timeout_ = false;
  }

  void on_watchdog() {
    if (last_cmd_time_.nanoseconds() == 0) {
      return;
    }

    const double dt = (now() - last_cmd_time_).seconds();
    if (dt > cmd_timeout_sec_ && !sent_stop_after_timeout_) {
      publish_stop();
      sent_stop_after_timeout_ = true;
      RCLCPP_WARN(get_logger(),
                  "cmd_vel timeout (%.3f s): sent STOP to /api/sport/request", dt);
    }
  }

  rclcpp::Publisher<unitree_api::msg::Request>::SharedPtr req_pub_;
  rclcpp::Subscription<geometry_msgs::msg::Twist>::SharedPtr cmd_vel_sub_;
  rclcpp::TimerBase::SharedPtr watchdog_timer_;

  double max_vx_;
  double max_vy_;
  double max_wz_;
  double cmd_timeout_sec_;

  rclcpp::Time last_cmd_time_{0, 0, RCL_ROS_TIME};
  bool sent_stop_after_timeout_{false};
};

int main(int argc, char **argv) {
  rclcpp::init(argc, argv);
  auto node = std::make_shared<CmdVelToUnitreeBridge>();
  rclcpp::spin(node);
  rclcpp::shutdown();
  return 0;
}
