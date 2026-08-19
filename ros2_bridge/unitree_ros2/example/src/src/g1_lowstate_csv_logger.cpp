#include "rclcpp/rclcpp.hpp"
#include "unitree_hg/msg/imu_state.hpp"
#include "unitree_hg/msg/low_state.hpp"
#include "unitree_hg/msg/motor_state.hpp"

#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <memory>
#include <string>

class LowStateCsvSuber : public rclcpp::Node {
 public:
  LowStateCsvSuber(const std::string &topic_name, const std::string &csv_path, int max_samples)
      : Node("low_state_csv_suber"), max_samples_(max_samples) {
    fp_ = std::fopen(csv_path.c_str(), "w");
    if (!fp_) throw std::runtime_error("cannot open csv");
    std::fprintf(fp_, "wall_time_ns");
    for (int i = 0; i < 12; i++) std::fprintf(fp_, ",q%d", i);
    for (int i = 0; i < 12; i++) std::fprintf(fp_, ",dq%d", i);
    for (int i = 0; i < 12; i++) std::fprintf(fp_, ",tau%d", i);
    std::fprintf(fp_, ",imu_roll,imu_pitch,imu_yaw,acc_x,acc_y,acc_z,gyro_x,gyro_y,gyro_z\n");
    std::fflush(fp_);
    suber_ = this->create_subscription<unitree_hg::msg::LowState>(
        topic_name, 10,
        [this](const unitree_hg::msg::LowState::SharedPtr data) { topic_callback(data); });
    RCLCPP_INFO(this->get_logger(), "CSV lowstate logger topic=%s motors=12 wall_time_only", topic_name.c_str());
  }
  ~LowStateCsvSuber() override { if (fp_) { std::fflush(fp_); std::fclose(fp_); } }
 private:
  void topic_callback(const unitree_hg::msg::LowState::SharedPtr &data) {
    imu_ = data->imu_state;
    for (int i = 0; i < 12; i++) motor_[i] = data->motor_state[i];
    auto wall_ns = std::chrono::duration_cast<std::chrono::nanoseconds>(std::chrono::system_clock::now().time_since_epoch()).count();
    std::fprintf(fp_, "%ld", (long)wall_ns);
    for (int i = 0; i < 12; i++) std::fprintf(fp_, ",%.9f", motor_[i].q);
    for (int i = 0; i < 12; i++) std::fprintf(fp_, ",%.9f", motor_[i].dq);
    for (int i = 0; i < 12; i++) std::fprintf(fp_, ",%.9f", motor_[i].tau_est);
    std::fprintf(fp_, ",%.9f,%.9f,%.9f,%.9f,%.9f,%.9f,%.9f,%.9f,%.9f\n", imu_.rpy[0], imu_.rpy[1], imu_.rpy[2], imu_.accelerometer[0], imu_.accelerometer[1], imu_.accelerometer[2], imu_.gyroscope[0], imu_.gyroscope[1], imu_.gyroscope[2]);
    samples_++;
    if (samples_ % 100 == 0) std::fflush(fp_);
    if (max_samples_ > 0 && samples_ >= max_samples_) { std::fflush(fp_); rclcpp::shutdown(); }
  }
  rclcpp::Subscription<unitree_hg::msg::LowState>::SharedPtr suber_;
  unitree_hg::msg::IMUState imu_;
  unitree_hg::msg::MotorState motor_[35];
  FILE *fp_ = nullptr;
  int max_samples_;
  int samples_ = 0;
};
int main(int argc, char *argv[]) {
  rclcpp::init(argc, argv);
  std::string topic_name = argc > 1 ? argv[1] : "lowstate";
  std::string csv_path = argc > 2 ? argv[2] : "/tmp/g1_lowstate.csv";
  int max_samples = argc > 3 ? std::atoi(argv[3]) : 0;
  rclcpp::spin(std::make_shared<LowStateCsvSuber>(topic_name, csv_path, max_samples));
  rclcpp::shutdown();
  return 0;
}
