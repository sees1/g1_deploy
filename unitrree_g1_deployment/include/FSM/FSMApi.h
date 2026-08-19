#pragma once

#include <algorithm>
#include <array>
#include <atomic>
#include <chrono>
#include <cctype>
#include <cerrno>
#include <cstdlib>
#include <cstring>
#include <mutex>
#include <optional>
#include <sstream>
#include <string>
#include <thread>
#include <unordered_map>
#include <vector>

#include <arpa/inet.h>
#include <netinet/in.h>
#include <sys/select.h>
#include <sys/socket.h>
#include <unistd.h>

#include <spdlog/spdlog.h>
#include <yaml-cpp/yaml.h>

#include "BaseState.h"

class FSMApi
{
public:
    struct VelocityCommandSample
    {
        std::array<float, 3> command {0.0f, 0.0f, 0.0f};
        bool recent = false;
        bool active = false;
    };

    static FSMApi& instance()
    {
        static FSMApi api;
        return api;
    }

    void configure(const YAML::Node& cfg)
    {
        std::lock_guard<std::mutex> lock(mutex_);
        enabled_ = cfg && cfg["enabled"] ? cfg["enabled"].as<bool>() : false;
        host_ = cfg && cfg["host"] ? cfg["host"].as<std::string>() : "127.0.0.1";
        port_ = cfg && cfg["port"] ? cfg["port"].as<int>() : 8080;
        cmd_vel_timeout_sec_ = cfg && cfg["cmd_vel_timeout_sec"] ? cfg["cmd_vel_timeout_sec"].as<float>() : 0.5f;
    }

    void setAvailableStates(const std::vector<std::string>& states)
    {
        std::lock_guard<std::mutex> lock(mutex_);
        available_states_ = states;
        available_policies_.clear();
        for (const auto& state : available_states_) {
            if (state != "Passive" && state != "FixStand") {
                available_policies_.push_back(state);
            }
        }
    }

    void setCurrentState(const std::string& state)
    {
        std::lock_guard<std::mutex> lock(mutex_);
        current_state_ = state;
    }

    void setCurrentStateContext(const std::string& state, const std::vector<std::string>& allowed_targets)
    {
        std::lock_guard<std::mutex> lock(mutex_);
        current_state_ = state;
        allowed_targets_ = allowed_targets;
    }

    std::optional<int> consumeRequestedState()
    {
        std::lock_guard<std::mutex> lock(mutex_);
        if (!requested_state_id_) {
            return std::nullopt;
        }
        auto requested = requested_state_id_;
        requested_state_id_.reset();
        requested_state_name_.clear();
        return requested;
    }

    bool requestState(int state_id, const std::string& state_name, std::string* error = nullptr)
    {
        std::lock_guard<std::mutex> lock(mutex_);
        if (!contains(available_states_, state_name)) {
            if (error) *error = "unknown state";
            return false;
        }
        requested_state_id_ = state_id;
        requested_state_name_ = state_name;
        return true;
    }

    void clearRequestedState()
    {
        std::lock_guard<std::mutex> lock(mutex_);
        requested_state_id_.reset();
        requested_state_name_.clear();
    }

    void setVelocityCommand(float vx, float vy, float wz)
    {
        std::lock_guard<std::mutex> lock(mutex_);
        velocity_command_ = {vx, vy, wz};
        velocity_command_timestamp_ = std::chrono::steady_clock::now();
        velocity_command_received_ = true;
    }

    VelocityCommandSample velocityCommandSample() const
    {
        std::lock_guard<std::mutex> lock(mutex_);
        VelocityCommandSample sample;
        sample.active = enabled_;
        sample.command = velocity_command_;
        if (!velocity_command_received_) {
            return sample;
        }

        const auto age = std::chrono::duration_cast<std::chrono::duration<float>>(
            std::chrono::steady_clock::now() - velocity_command_timestamp_
        ).count();
        sample.recent = age <= cmd_vel_timeout_sec_;
        return sample;
    }

    void start()
    {
        std::lock_guard<std::mutex> lock(mutex_);
        if (!enabled_ || running_) {
            return;
        }
        running_ = true;
        server_thread_ = std::thread([this] { serverLoop(); });
    }

    void stop()
    {
        {
            std::lock_guard<std::mutex> lock(mutex_);
            if (!running_) {
                return;
            }
            running_ = false;
        }

        if (listen_fd_ >= 0) {
            ::shutdown(listen_fd_, SHUT_RDWR);
            ::close(listen_fd_);
            listen_fd_ = -1;
        }

        if (server_thread_.joinable()) {
            server_thread_.join();
        }
    }

    ~FSMApi()
    {
        stop();
    }

private:
    FSMApi() = default;
    FSMApi(const FSMApi&) = delete;
    FSMApi& operator=(const FSMApi&) = delete;

    static bool contains(const std::vector<std::string>& items, const std::string& value)
    {
        return std::find(items.begin(), items.end(), value) != items.end();
    }

    static std::string trim(const std::string& value)
    {
        size_t start = 0;
        while (start < value.size() && std::isspace(static_cast<unsigned char>(value[start]))) {
            ++start;
        }
        size_t end = value.size();
        while (end > start && std::isspace(static_cast<unsigned char>(value[end - 1]))) {
            --end;
        }
        return value.substr(start, end - start);
    }

    static std::string jsonEscape(const std::string& value)
    {
        std::string out;
        out.reserve(value.size());
        for (char ch : value) {
            switch (ch) {
            case '\\': out += "\\\\"; break;
            case '"': out += "\\\""; break;
            case '\n': out += "\\n"; break;
            case '\r': out += "\\r"; break;
            case '\t': out += "\\t"; break;
            default: out += ch; break;
            }
        }
        return out;
    }

    static std::string urlDecode(const std::string& value)
    {
        std::string out;
        out.reserve(value.size());
        for (size_t i = 0; i < value.size(); ++i) {
            if (value[i] == '%' && i + 2 < value.size()) {
                const auto hex = value.substr(i + 1, 2);
                char* end = nullptr;
                const long code = std::strtol(hex.c_str(), &end, 16);
                if (end != nullptr && *end == '\0') {
                    out.push_back(static_cast<char>(code));
                    i += 2;
                    continue;
                }
            }
            out.push_back(value[i] == '+' ? ' ' : value[i]);
        }
        return out;
    }

    static std::unordered_map<std::string, std::string> parseQuery(const std::string& query)
    {
        std::unordered_map<std::string, std::string> result;
        std::stringstream ss(query);
        std::string item;
        while (std::getline(ss, item, '&')) {
            const auto pos = item.find('=');
            if (pos == std::string::npos) {
                continue;
            }
            result[item.substr(0, pos)] = urlDecode(item.substr(pos + 1));
        }
        return result;
    }

    static std::string extractJsonString(const std::string& body, const std::string& key)
    {
        const auto needle = "\"" + key + "\"";
        auto key_pos = body.find(needle);
        if (key_pos == std::string::npos) {
            return "";
        }
        auto colon_pos = body.find(':', key_pos + needle.size());
        if (colon_pos == std::string::npos) {
            return "";
        }
        auto first_quote = body.find('"', colon_pos + 1);
        if (first_quote == std::string::npos) {
            return "";
        }
        auto second_quote = body.find('"', first_quote + 1);
        if (second_quote == std::string::npos) {
            return "";
        }
        return body.substr(first_quote + 1, second_quote - first_quote - 1);
    }

    static std::optional<float> parseFloatValue(const std::string& value)
    {
        if (value.empty()) {
            return std::nullopt;
        }

        char* end = nullptr;
        const float parsed = std::strtof(value.c_str(), &end);
        if (end == nullptr || *end != '\0') {
            return std::nullopt;
        }
        return parsed;
    }

    static std::optional<float> extractJsonFloat(const std::string& body, const std::string& key)
    {
        const auto needle = "\"" + key + "\"";
        auto key_pos = body.find(needle);
        if (key_pos == std::string::npos) {
            return std::nullopt;
        }
        auto colon_pos = body.find(':', key_pos + needle.size());
        if (colon_pos == std::string::npos) {
            return std::nullopt;
        }

        auto value_start = body.find_first_not_of(" \t\r\n", colon_pos + 1);
        if (value_start == std::string::npos) {
            return std::nullopt;
        }

        auto value_end = body.find_first_of(",}\r\n", value_start);
        const auto token = trim(body.substr(value_start, value_end - value_start));
        return parseFloatValue(token);
    }

    std::string statusJson()
    {
        std::lock_guard<std::mutex> lock(mutex_);
        bool cmd_vel_recent = false;
        if (velocity_command_received_) {
            const auto age = std::chrono::duration_cast<std::chrono::duration<float>>(
                std::chrono::steady_clock::now() - velocity_command_timestamp_
            ).count();
            cmd_vel_recent = age <= cmd_vel_timeout_sec_;
        }
        std::ostringstream out;
        out << "{";
        out << "\"enabled\":" << (enabled_ ? "true" : "false") << ",";
        out << "\"current_state\":\"" << jsonEscape(current_state_) << "\",";
        out << "\"requested_state\":\"" << jsonEscape(requested_state_name_) << "\",";
        out << "\"allowed_targets\":[";
        for (size_t i = 0; i < allowed_targets_.size(); ++i) {
            if (i > 0) out << ",";
            out << "\"" << jsonEscape(allowed_targets_[i]) << "\"";
        }
        out << "],";
        out << "\"available_states\":[";
        for (size_t i = 0; i < available_states_.size(); ++i) {
            if (i > 0) out << ",";
            out << "\"" << jsonEscape(available_states_[i]) << "\"";
        }
        out << "],";
        out << "\"available_policies\":[";
        for (size_t i = 0; i < available_policies_.size(); ++i) {
            if (i > 0) out << ",";
            out << "\"" << jsonEscape(available_policies_[i]) << "\"";
        }
        out << "],";
        out << "\"cmd_vel\":{";
        out << "\"vx\":" << velocity_command_[0] << ",";
        out << "\"vy\":" << velocity_command_[1] << ",";
        out << "\"wz\":" << velocity_command_[2] << ",";
        out << "\"recent\":" << (cmd_vel_recent ? "true" : "false");
        out << "}";
        out << "}";
        return out.str();
    }

    std::string requestTransition(const std::string& requested_state, int& status_code)
    {
        const auto clean_state = trim(requested_state);
        if (clean_state.empty()) {
            status_code = 400;
            return "{\"ok\":false,\"error\":\"state is required\"}";
        }

        if (!FSMStringMap.right.count(clean_state)) {
            status_code = 404;
            return "{\"ok\":false,\"error\":\"state not enabled\"}";
        }

        {
            std::lock_guard<std::mutex> lock(mutex_);
            if (clean_state == current_state_) {
                status_code = 200;
                return "{\"ok\":true,\"message\":\"already in requested state\"}";
            }
            if (!allowed_targets_.empty() && !contains(allowed_targets_, clean_state)) {
                status_code = 409;
                return "{\"ok\":false,\"error\":\"transition is not allowed from current state\"}";
            }
        }

        std::string error;
        const bool accepted = requestState(FSMStringMap.right.at(clean_state), clean_state, &error);
        if (!accepted) {
            status_code = 400;
            return "{\"ok\":false,\"error\":\"" + jsonEscape(error) + "\"}";
        }

        status_code = 202;
        return "{\"ok\":true,\"requested_state\":\"" + jsonEscape(clean_state) + "\"}";
    }

    std::string cmdVelJson()
    {
        const auto sample = velocityCommandSample();
        float timeout_sec = 0.5f;
        {
            std::lock_guard<std::mutex> lock(mutex_);
            timeout_sec = cmd_vel_timeout_sec_;
        }
        std::ostringstream out;
        out << "{";
        out << "\"ok\":true,";
        out << "\"vx\":" << sample.command[0] << ",";
        out << "\"vy\":" << sample.command[1] << ",";
        out << "\"wz\":" << sample.command[2] << ",";
        out << "\"recent\":" << (sample.recent ? "true" : "false") << ",";
        out << "\"timeout_sec\":" << timeout_sec;
        out << "}";
        return out.str();
    }

    std::string updateCmdVel(
        const std::unordered_map<std::string, std::string>& query_params,
        const std::string& request_body,
        int& status_code)
    {
        auto vx = query_params.count("vx") ? parseFloatValue(query_params.at("vx")) : std::nullopt;
        auto vy = query_params.count("vy") ? parseFloatValue(query_params.at("vy")) : std::nullopt;
        auto wz = query_params.count("wz") ? parseFloatValue(query_params.at("wz")) : std::nullopt;

        if (!vx) vx = extractJsonFloat(request_body, "vx");
        if (!vy) vy = extractJsonFloat(request_body, "vy");
        if (!wz) wz = extractJsonFloat(request_body, "wz");

        if (!vx || !vy || !wz) {
            status_code = 400;
            return "{\"ok\":false,\"error\":\"vx, vy and wz are required\"}";
        }

        setVelocityCommand(*vx, *vy, *wz);
        status_code = 202;
        return cmdVelJson();
    }

    void sendResponse(int client_fd, int status_code, const std::string& body)
    {
        const char* status_text = "OK";
        switch (status_code) {
        case 202: status_text = "Accepted"; break;
        case 400: status_text = "Bad Request"; break;
        case 404: status_text = "Not Found"; break;
        case 405: status_text = "Method Not Allowed"; break;
        case 409: status_text = "Conflict"; break;
        case 500: status_text = "Internal Server Error"; break;
        default: break;
        }

        std::ostringstream response;
        response << "HTTP/1.1 " << status_code << " " << status_text << "\r\n";
        response << "Content-Type: application/json\r\n";
        response << "Content-Length: " << body.size() << "\r\n";
        response << "Connection: close\r\n\r\n";
        response << body;
        const auto response_str = response.str();
        ::send(client_fd, response_str.c_str(), response_str.size(), 0);
    }

    void handleClient(int client_fd)
    {
        std::string request;
        char buffer[4096];
        while (true) {
            const auto bytes = ::recv(client_fd, buffer, sizeof(buffer), 0);
            if (bytes <= 0) {
                break;
            }
            request.append(buffer, bytes);
            const auto header_end = request.find("\r\n\r\n");
            if (header_end == std::string::npos) {
                continue;
            }

            size_t content_length = 0;
            const auto content_length_pos = request.find("Content-Length:");
            if (content_length_pos != std::string::npos) {
                auto line_end = request.find("\r\n", content_length_pos);
                auto value = trim(request.substr(content_length_pos + 15, line_end - (content_length_pos + 15)));
                try {
                    content_length = static_cast<size_t>(std::stoul(value));
                } catch (...) {
                    content_length = 0;
                }
            }

            const size_t body_start = header_end + 4;
            if (request.size() >= body_start + content_length) {
                break;
            }
        }

        std::istringstream stream(request);
        std::string method;
        std::string target;
        std::string version;
        stream >> method >> target >> version;

        int status_code = 200;
        std::string body;
        const auto header_end = request.find("\r\n\r\n");
        const std::string request_body = header_end == std::string::npos ? "" : request.substr(header_end + 4);

        std::string path = target;
        std::string query;
        std::unordered_map<std::string, std::string> query_params;
        if (const auto pos = target.find('?'); pos != std::string::npos) {
            path = target.substr(0, pos);
            query = target.substr(pos + 1);
            query_params = parseQuery(query);
        }

        if (method == "GET" && (path == "/api/fsm" || path == "/api/policies")) {
            body = statusJson();
        } else if (method == "GET" && (path == "/cmd_vel" || path == "/api/cmd_vel")) {
            body = cmdVelJson();
        } else if ((method == "POST" || method == "GET") && (path == "/cmd_vel" || path == "/api/cmd_vel")) {
            body = updateCmdVel(query_params, request_body, status_code);
        } else if ((method == "POST" || method == "GET") && (path == "/api/fsm/transition" || path == "/api/policies/switch")) {
            std::string requested_state;
            if (query_params.count("state")) {
                requested_state = query_params["state"];
            }
            if (requested_state.empty()) {
                requested_state = extractJsonString(request_body, "state");
            }
            if (requested_state.empty()) {
                requested_state = request_body;
            }
            body = requestTransition(requested_state, status_code);
        } else if (path.rfind("/api/", 0) == 0) {
            status_code = 404;
            body = "{\"ok\":false,\"error\":\"unknown endpoint\"}";
        } else {
            status_code = 404;
            body = "{\"ok\":false,\"error\":\"not found\"}";
        }

        sendResponse(client_fd, status_code, body);
    }

    void serverLoop()
    {
        int listen_fd = ::socket(AF_INET, SOCK_STREAM, 0);
        if (listen_fd < 0) {
            spdlog::error("FSM API: failed to create socket: {}", std::strerror(errno));
            std::lock_guard<std::mutex> lock(mutex_);
            running_ = false;
            return;
        }

        int opt = 1;
        ::setsockopt(listen_fd, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt));

        sockaddr_in addr {};
        addr.sin_family = AF_INET;
        addr.sin_port = htons(static_cast<uint16_t>(port_));
        if (::inet_pton(AF_INET, host_.c_str(), &addr.sin_addr) != 1) {
            spdlog::error("FSM API: invalid host '{}'", host_);
            ::close(listen_fd);
            std::lock_guard<std::mutex> lock(mutex_);
            running_ = false;
            return;
        }

        if (::bind(listen_fd, reinterpret_cast<sockaddr*>(&addr), sizeof(addr)) < 0) {
            spdlog::error("FSM API: bind {}:{} failed: {}", host_, port_, std::strerror(errno));
            ::close(listen_fd);
            std::lock_guard<std::mutex> lock(mutex_);
            running_ = false;
            return;
        }

        if (::listen(listen_fd, 8) < 0) {
            spdlog::error("FSM API: listen failed: {}", std::strerror(errno));
            ::close(listen_fd);
            std::lock_guard<std::mutex> lock(mutex_);
            running_ = false;
            return;
        }

        listen_fd_ = listen_fd;
        spdlog::info("FSM API: listening on http://{}:{}", host_, port_);

        while (running_) {
            fd_set readfds;
            FD_ZERO(&readfds);
            FD_SET(listen_fd, &readfds);
            timeval timeout {};
            timeout.tv_sec = 0;
            timeout.tv_usec = 200000;

            const int ready = ::select(listen_fd + 1, &readfds, nullptr, nullptr, &timeout);
            if (ready <= 0) {
                continue;
            }

            sockaddr_in client_addr {};
            socklen_t client_len = sizeof(client_addr);
            const int client_fd = ::accept(listen_fd, reinterpret_cast<sockaddr*>(&client_addr), &client_len);
            if (client_fd < 0) {
                continue;
            }

            handleClient(client_fd);
            ::close(client_fd);
        }

        if (listen_fd >= 0) {
            ::close(listen_fd);
        }
        listen_fd_ = -1;
    }

    mutable std::mutex mutex_;
    bool enabled_ = false;
    std::string host_ = "127.0.0.1";
    int port_ = 8080;
    std::vector<std::string> available_states_;
    std::vector<std::string> available_policies_;
    std::vector<std::string> allowed_targets_;
    std::string current_state_;
    std::optional<int> requested_state_id_;
    std::string requested_state_name_;
    std::array<float, 3> velocity_command_ {0.0f, 0.0f, 0.0f};
    bool velocity_command_received_ = false;
    float cmd_vel_timeout_sec_ = 0.5f;
    std::chrono::steady_clock::time_point velocity_command_timestamp_ = std::chrono::steady_clock::now();
    std::atomic<bool> running_ = false;
    std::thread server_thread_;
    std::atomic<int> listen_fd_ = -1;
};
