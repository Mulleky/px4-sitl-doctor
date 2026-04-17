# Changelog

All notable changes to this project will be documented here.

## [0.1.0] — 2026-04-16

### Added
- Initial release
- OS version checker (Ubuntu 22.04, 24.04, Windows WSL2, native)
- Python version and virtual environment checker
- ROS 2 distro detection and version compatibility checker
- Gazebo binary and version checker with ROS2+Gazebo combo validation
- PX4-Autopilot repository detection and SITL build state checker
- MicroXRCEAgent binary, version, and port 8888 checker
- Environment variable checker (GZ_SIM_*, AMENT_PREFIX_PATH, ROS_DOMAIN_ID)
- Shared library checker (libGstCameraSystem.so, libgps.so, libpx4.so)
- UDP/TCP port availability checker (14540, 14541, 8888, 7447)
- ROS 2 workspace build state checker (px4_msgs, px4_ros_com)
- Network connectivity checker (Internet, GitHub, PyPI)
- WSL2-specific checker (WSL2 kernel, X11, systemd, memory)
- Rich-based colour terminal report with plain/JSON/Markdown fallbacks
- Compatibility matrix (`data/compatibility.yaml`) with 3 version combos
- `--update-matrix` flag to fetch latest rules from GitHub
- `list-combos` subcommand
- Exit codes: 0 (pass), 1 (warn), 2 (fail)
