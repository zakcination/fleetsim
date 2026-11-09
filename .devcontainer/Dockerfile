# ROS 2 Jazzy (Ubuntu 24.04, Python 3.12). Used from v0.2 on for the ROS 2 layer;
# v0.1 only needs the Python package, which is installed into a venv that can also see rclpy.
FROM ros:jazzy

RUN apt-get update \
 && apt-get install -y --no-install-recommends python3-pip python3-venv git ffmpeg \
 && rm -rf /var/lib/apt/lists/*

RUN python3 -m venv --system-site-packages /opt/venv
ENV PATH="/opt/venv/bin:${PATH}"
