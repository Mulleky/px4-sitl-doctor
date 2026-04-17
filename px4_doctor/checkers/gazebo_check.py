"""Gazebo binary detection and version checker."""

from __future__ import annotations

import os
import re
from pathlib import Path

from px4_doctor.checkers.base import BaseChecker
from px4_doctor.models.result import CheckResult
from px4_doctor.platform_utils import detect_platform, find_binary, parse_version, run_cmd

_SKIP_PLATFORMS = {"windows_native", "macos"}

# Gazebo major version → codename
_MAJOR_TO_NAME = {8: "harmonic", 9: "ionic", 7: "garden", 6: "fortress"}


def _detect_gazebo() -> tuple[str | None, object | None]:
    """Return (binary_name_used, parsed_version) or (None, None)."""
    for binary in ("gz", "ign"):
        if find_binary(binary):
            rc, stdout, stderr = run_cmd([binary, "--version"])
            combined = stdout + stderr
            # Look for version number in output
            m = re.search(r"(\d+\.\d+\.\d+)", combined)
            if m:
                ver = parse_version(m.group(1))
                return binary, ver
            # Fallback: version present but in unusual format
            return binary, None
    return None, None


class GazeboChecker(BaseChecker):
    name = "Gazebo"
    category = "core"
    platforms = ["ubuntu_22_04", "ubuntu_24_04", "ubuntu_other", "windows_wsl2"]

    def __init__(self, matrix=None, ros2_distro: str | None = None) -> None:
        self._matrix = matrix
        self._platform = detect_platform()
        self._ros2_distro = ros2_distro or os.environ.get("ROS_DISTRO", "")

    def run(self) -> list[CheckResult]:
        if self._platform in _SKIP_PLATFORMS:
            return [self.skip(
                "Gazebo checks skipped on Windows native. Run inside WSL2."
            )]

        results: list[CheckResult] = []

        # 1. Binary present?
        binary, version = _detect_gazebo()
        if binary is None:
            results.append(CheckResult(
                checker_name="Gazebo Binary",
                status="fail",
                message="Gazebo binary ('gz' or 'ign') not found on PATH",
                fix=(
                    "Install Gazebo Harmonic:\n"
                    "  sudo apt install gz-harmonic\n"
                    "Or follow: https://gazebosim.org/docs/harmonic/install"
                ),
            ))
            return results

        if version is None:
            results.append(CheckResult(
                checker_name="Gazebo Binary",
                status="warn",
                message=f"'{binary}' found but version could not be parsed",
                fix="Ensure Gazebo is correctly installed.",
            ))
        else:
            major = version.major
            codename = _MAJOR_TO_NAME.get(major, f"unknown (major={major})")
            results.append(CheckResult(
                checker_name="Gazebo Binary",
                status="pass",
                message=f"gz {version} ({codename}) found",
                detail=f"Binary: {binary}",
            ))

            # 2. ROS 2 + Gazebo compatibility
            if self._matrix and self._ros2_distro and version:
                codename_key = _MAJOR_TO_NAME.get(version.major)
                if codename_key:
                    if self._matrix.is_ros2_gazebo_compatible(self._ros2_distro, codename_key):
                        results.append(CheckResult(
                            checker_name="ROS2 + Gazebo Combo",
                            status="pass",
                            message=(
                                f"{self._ros2_distro} + {codename_key} — "
                                "compatible combo found in matrix"
                            ),
                        ))
                    else:
                        results.append(CheckResult(
                            checker_name="ROS2 + Gazebo Combo",
                            status="fail",
                            message=(
                                f"{self._ros2_distro} + {codename_key} is NOT a "
                                "known-compatible combination"
                            ),
                            fix=(
                                "Supported combos:\n"
                                "  ROS 2 Humble  + Gazebo Harmonic (Ubuntu 22.04/24.04)\n"
                                "  ROS 2 Jazzy   + Gazebo Harmonic (Ubuntu 24.04)\n"
                                "  ROS 2 Jazzy   + Gazebo Ionic    (Ubuntu 24.04)"
                            ),
                        ))

        # 3. GZ_SIM_RESOURCE_PATH
        resource_path = os.environ.get("GZ_SIM_RESOURCE_PATH", "")
        if resource_path:
            if Path(resource_path.split(":")[0]).exists():
                results.append(CheckResult(
                    checker_name="GZ_SIM_RESOURCE_PATH",
                    status="pass",
                    message=f"GZ_SIM_RESOURCE_PATH set and path exists: {resource_path[:60]}",
                ))
            else:
                results.append(CheckResult(
                    checker_name="GZ_SIM_RESOURCE_PATH",
                    status="warn",
                    message=f"GZ_SIM_RESOURCE_PATH is set but path does not exist: {resource_path}",
                    fix="Build PX4 first or correct the path in ~/.bashrc",
                ))
        else:
            results.append(CheckResult(
                checker_name="GZ_SIM_RESOURCE_PATH",
                status="fail",
                message="GZ_SIM_RESOURCE_PATH is not set — Gazebo cannot find PX4 models/worlds",
                fix=(
                    "Add to ~/.bashrc:\n"
                    "  export GZ_SIM_RESOURCE_PATH=$HOME/PX4-Autopilot/Tools/simulation/gz/models"
                ),
            ))

        # 4. GZ_SIM_SYSTEM_PLUGIN_PATH
        plugin_path = os.environ.get("GZ_SIM_SYSTEM_PLUGIN_PATH", "")
        if plugin_path:
            results.append(CheckResult(
                checker_name="GZ_SIM_SYSTEM_PLUGIN_PATH",
                status="pass",
                message=f"GZ_SIM_SYSTEM_PLUGIN_PATH set: {plugin_path[:60]}",
            ))
        else:
            results.append(CheckResult(
                checker_name="GZ_SIM_SYSTEM_PLUGIN_PATH",
                status="fail",
                message="GZ_SIM_SYSTEM_PLUGIN_PATH is not set — PX4 Gazebo plugins will not load",
                fix=(
                    "Add to ~/.bashrc:\n"
                    "  export GZ_SIM_SYSTEM_PLUGIN_PATH="
                    "$HOME/PX4-Autopilot/build/px4_sitl_default/lib"
                ),
            ))

        # 5. Camera plugin
        camera_lib = "libGstCameraSystem.so"
        search_dirs = [
            Path.home() / ".gz" / "sim" / "plugins",
            Path.home() / "PX4-Autopilot" / "build" / "px4_sitl_default" / "lib",
        ]
        if plugin_path:
            for p in plugin_path.split(":"):
                search_dirs.append(Path(p))

        found_camera = any((d / camera_lib).exists() for d in search_dirs)
        if found_camera:
            results.append(CheckResult(
                checker_name="Gazebo Camera Plugin",
                status="pass",
                message=f"{camera_lib} found",
            ))
        else:
            results.append(CheckResult(
                checker_name="Gazebo Camera Plugin",
                status="warn",
                message=f"{camera_lib} not found — camera SITL will not work",
                fix="cd ~/PX4-Autopilot && make px4_sitl gz_x500_mono_cam",
            ))

        return results
