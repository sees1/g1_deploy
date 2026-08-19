from setuptools import find_packages, setup


package_name = "robot_ws_bridge"


setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", [f"resource/{package_name}"]),
        (f"share/{package_name}", ["package.xml"]),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="robot-team",
    maintainer_email="devnull@example.com",
    description="WS сервер на роботе как ROS2 node: JSON команды → ROS2, статусы → WS.",
    license="Apache-2.0",
    tests_require=["pytest"],
    entry_points={
        "console_scripts": [
            "robot_ws_bridge = robot_ws_bridge.main:main",
        ],
    },
)

