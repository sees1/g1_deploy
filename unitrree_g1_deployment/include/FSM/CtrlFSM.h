// Copyright (c) 2025, Unitree Robotics Co., Ltd.
// All rights reserved.

#pragma once

#include <algorithm>
#include <unitree/common/thread/recurrent_thread.hpp>
#include "BaseState.h"
#include "FSMApi.h"
#include "param.h"
#include <spdlog/spdlog.h>
#include <yaml-cpp/yaml.h>

class CtrlFSM
{
public:
    CtrlFSM(std::shared_ptr<BaseState> initstate)
    {
        // Initialize FSM states
        states.push_back(std::move(initstate));

    }

    CtrlFSM(YAML::Node cfg)
    {
        auto fsms = cfg["_"]; // enabled FSMs

        // register FSM string map; used for state transition
        for (auto it = fsms.begin(); it != fsms.end(); ++it)
        {
            std::string fsm_name = it->first.as<std::string>();
            int id = it->second["id"].as<int>();
            FSMStringMap.insert({id, fsm_name});
        }

        // Initialize FSM states
        for (auto it = fsms.begin(); it != fsms.end(); ++it)
        {
            std::string fsm_name = it->first.as<std::string>();
            int id = it->second["id"].as<int>();
            std::string fsm_type = it->second["type"] ? it->second["type"].as<std::string>() : fsm_name;
            auto fsm_class = getFsmMap().find("State_" + fsm_type);
            if (fsm_class == getFsmMap().end()) {
                throw std::runtime_error("FSM: Unknown FSM type " + fsm_type);
            }
            auto state_instance = fsm_class->second(id, fsm_name);
            add(state_instance);
        }

        FSMApi::instance().configure(param::config["api"]);
        std::vector<std::string> state_names;
        state_names.reserve(states.size());
        for (const auto& state : states) {
            state_names.push_back(state->getStateString());
        }
        FSMApi::instance().setAvailableStates(state_names);
    }

    void start() 
    {
        // Start From State_Passive
        currentState = states[0];
        currentState->enter();
        publishStateContext_();
        FSMApi::instance().start();

        fsm_thread_ = std::make_shared<unitree::common::RecurrentThread>(
            "FSM", 0, this->dt * 1e6, &CtrlFSM::run_, this);
        spdlog::info("FSM: Start {}", currentState->getStateString());
    }

    void add(std::shared_ptr<BaseState> state)
    {
        for(auto & s : states)
        {
            if(s->isState(state->getState()))
            {
                spdlog::error("FSM: State_{} already exists", state->getStateString());
                std::exit(0);
            }
        }

        states.push_back(std::move(state));
    }
    
    ~CtrlFSM()
    {
        FSMApi::instance().stop();
        states.clear();
    }

    std::vector<std::shared_ptr<BaseState>> states;
private:
    const double dt = 0.001;

    void run_()
    {
        currentState->pre_run();
        currentState->run();
        currentState->post_run();
        
        // Check if need to change state
        int nextStateMode = 0;
        if (auto requested_state = FSMApi::instance().consumeRequestedState()) {
            if (*requested_state == currentState->getState()) {
                nextStateMode = 0;
            } else if (currentState->canTransitionTo(*requested_state)) {
                nextStateMode = *requested_state;
            } else {
                spdlog::warn(
                    "FSM API: transition from {} to {} is not allowed",
                    currentState->getStateString(),
                    FSMStringMap.left.at(*requested_state)
                );
            }
        }

        for(int i(0); nextStateMode == 0 && i<currentState->registered_checks.size(); i++)
        {
            if(currentState->registered_checks[i].first())
            {
                nextStateMode = currentState->registered_checks[i].second;
                break;
            }
        }

        if(nextStateMode != 0 && !currentState->isState(nextStateMode))
        {
            for(auto & state : states)
            {
                if(state->isState(nextStateMode))
                {
                    spdlog::info("FSM: Change state from {} to {}", currentState->getStateString(), state->getStateString());
                    currentState->exit();
                    currentState = state;
                    currentState->enter();
                    publishStateContext_();
                    break;
                }
            }
        }
    }

    void publishStateContext_()
    {
        std::vector<std::string> allowed_targets;
        for (const auto& target_id : currentState->allowedTransitions()) {
            if (FSMStringMap.left.count(target_id)) {
                allowed_targets.push_back(FSMStringMap.left.at(target_id));
            }
        }
        std::sort(allowed_targets.begin(), allowed_targets.end());
        FSMApi::instance().setCurrentStateContext(currentState->getStateString(), allowed_targets);
    }

    std::shared_ptr<BaseState> currentState;
    unitree::common::RecurrentThreadPtr fsm_thread_;
};
