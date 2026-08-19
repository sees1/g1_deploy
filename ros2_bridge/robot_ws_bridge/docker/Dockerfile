FROM ros:humble-ros-base

SHELL ["/bin/bash", "-lc"]

ARG DEBIAN_FRONTEND=noninteractive

# Базовые инструменты для сборки ament_python пакета.
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3-pip \
    python3-venv \
    python3-colcon-common-extensions \
    && rm -rf /var/lib/apt/lists/*

# uv (быстрый менеджер зависимостей Python).
RUN pip3 install --no-cache-dir uv

WORKDIR /ws

# Копируем только пакет, чтобы Docker cache работал предсказуемо.
COPY . /ws/src/robot_ws_bridge

# Устанавливаем runtime зависимости Python через uv в системный python контейнера.
RUN cd /ws/src/robot_ws_bridge && uv pip install --system -r <(python3 -c "import tomllib; p=tomllib.load(open('pyproject.toml','rb')); print('\\n'.join(p['project']['dependencies']))")

# Собираем workspace.
RUN source /opt/ros/humble/setup.bash \
    && cd /ws \
    && colcon build --symlink-install

# По умолчанию запускаем node.
CMD ["bash", "-lc", "source /opt/ros/humble/setup.bash && source /ws/install/setup.bash && ros2 run robot_ws_bridge robot_ws_bridge"]

