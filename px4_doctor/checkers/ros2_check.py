"""ROS 2 distro detection and version checker."""

from __future__ import annotations

import os
import re
from pathlib import Path

from px4_doctor.checkers.base import BaseChecker
from px4_doctor.models.result import CheckResult
from px4_doctor.platform_utils import detect_platform, find_binary, run_cmd

_SKIP_PLATFORMS = {"windows_native", "macos"}
_KNOWN_DISTROS = {"humble", "iron", "jazzy", "rolling"}


def _detect_distro_from_binary() -> str | None:
    """Run 'ros2 --version' and parse the distro name."""
    rc, stdout, stderr = run_cmd(["ros2", "--version"])
    output = (stdout + stderr).lower()
    for distro in _KNOWN_DISTROS:
        if distro in output:
            return distro
    return None


def _detect_distro_from_opt() -> list[str]:
    """List installed distros under /opt/ros/."""
    opt_ros = Path("/opt/ros")
    if not opt_ros.exists():
        return []
    return [d.name for d in opt_ros.iterdir() if d.is_dir() and d.name in _KNOWN_DISTROS]


class ROS2Checker(BaseChecker):
    name = "ROS 2"
    category = "core"
    platforms = ["ubuntu_22_04", "ubuntu_24_04", "ubuntu_other", "windows_wsl2"]

    def __init__(self, matrix=None) -> None:
        self._matrix = matrix
        self._platform = detect_platform()

    def run(self) -> list[CheckResult]:
        if self._platform in _SKIP_PLATFORMS:
            return [self.skip(
                "ROS 2 is not supported on Windows native. "
                "Install WSL2 and run this check inside the WSL2 Ubuntu environment."
            )]

        results: list[CheckResult] = []

        # 1. Binary present?
        binary = find_binary("ros2")
        if not binary:
            results.append(CheckResult(
                checker_name="ROS 2 Binary",
                status="fail",
                message="'ros2' binary not found on PATH",
                fix=(
                    "Source your ROS 2 installation:\n"
                    "  source /opt/ros/humble/setup.bash\n"
                    "Or install ROS 2 Humble:\n"
                    "  sudo apt install ros-humble-desktop"
                ),
            ))
            # Cannot proceed without binary
            return results

        # 2. Detect distro from binary
        binary_distro = _detect_distro_from_binary()
        # 3. Detect installed distros from /opt/ros/
        opt_distros = _detect_distro_from_opt()

        if binary_distro:
            results.append(CheckResult(
                checker_name="ROS 2 Distro",
                status="pass",
                message=f"ROS 2 '{binary_distro}' detected from binary output",
            ))
        else:
            results.append(CheckResult(
                checker_name="ROS 2 Distro",
                status="warn",
                message="Could not parse ROS 2 distro name from 'ros2 --version' output",
                detail=(
                    f"Installed in /opt/ros: {opt_distros or 'none found'}. "
                    "Ensure the correct setup.bash is sourced."
                ),
                fix="source /opt/ros/humble/setup.bash  # adjust for your distro",
            ))

        # 4. ROS_DISTRO env var
        env_distro = os.environ.get("ROS_DISTRO", "")
        if not env_distro:
            results.append(CheckResult(
                checker_name="ROS_DISTRO env var",
                status="warn",
                message="ROS_DISTRO environment variable is not set",
                fix=(
                    "Source your ROS 2 workspace:\n"
                    "  source /opt/ros/humble/setup.bash\n"
                    "Add to ~/.bashrc to persist."
                ),
            ))
        elif binary_distro and env_distro.lower() != binary_distro.lower():
            results.append(CheckResult(
                checker_name="ROS_DISTRO env var",
                status="fail",
                message=(
                    f"ROS_DISTRO={env_distro!r} but binary reports '{binary_distro}' — mismatch!"
                ),
                fix=f"source /opt/ros/{binary_distro}/setup.bash",
            ))
        else:
            results.append(CheckResult(
                checker_name="ROS_DISTRO env var",
                status="pass",
                message=f"ROS_DISTRO={env_distro!r} — matches binary",
            ))

        # 5. AMENT_PREFIX_PATH (confirms workspace was sourced)
        if os.environ.get("AMENT_PREFIX_PATH"):
            results.append(CheckResult(
                checker_name="ROS 2 Sourced",
                status="pass",
                message="AMENT_PREFIX_PATH is set — ROS 2 workspace sourced",
            ))
        else:
            results.append(CheckResult(
                checker_name="ROS 2 Sourced",
                status="warn",
                message="AMENT_PREFIX_PATH not set — ROS 2 workspace may not be sourced",
                fix="source /opt/ros/humble/setup.bash  # Add to ~/.bashrc",
            ))

        # 6. Matrix compatibility
        if self._matrix and binary_distro:
            combos = self._matrix.get_combos()
            known_ros2 = {c["ros2"] for c in combos}
            if binary_distro not in known_ros2:
                results.append(CheckResult(
                    checker_name="ROS 2 Compatibility",
                    status="warn",
                    message=(
                        f"ROS 2 '{binary_distro}' is not listed in the compatibility matrix. "
                        f"Known distros: {sorted(known_ros2)}"
                    ),
                    fix="Use one of the tested ROS 2 distros: humble, jazzy",
                ))

        return results
