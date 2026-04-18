"""ROS 2 distro detection and version checker."""

from __future__ import annotations

import os
import re
from pathlib import Path

from px4_doctor.checkers.base import BaseChecker
from px4_doctor.models.result import CheckResult
from px4_doctor.platform_utils import detect_platform, find_binary, run_cmd

_SKIP_PLATFORMS = {"windows_native", "macos"}
_KNOWN_DISTROS = {"humble", "iron", "jazzy", "kilted", "rolling"}


def _detect_distro_from_binary() -> str | None:
    """Run 'ros2 --version' and parse the distro name."""
    rc, stdout, stderr = run_cmd(["ros2", "--version"])
    output = (stdout + stderr).lower()
    for distro in _KNOWN_DISTROS:
        if distro in output:
            return distro
    return None


def _detect_distro_from_env() -> str | None:
    """Return ROS_DISTRO env var if set and /opt/ros/<distro> exists."""
    distro = os.environ.get("ROS_DISTRO", "").lower().strip()
    if distro and Path(f"/opt/ros/{distro}").exists():
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
            return results

        # 2. Detect distro — try binary output first, then env+filesystem fallback
        binary_distro = _detect_distro_from_binary()
        opt_distros = _detect_distro_from_opt()
        env_distro = os.environ.get("ROS_DISTRO", "").lower().strip()

        if binary_distro:
            results.append(CheckResult(
                checker_name="ROS 2 Distro",
                status="pass",
                message=f"ROS 2 '{binary_distro}' detected from binary output",
            ))
            resolved_distro = binary_distro
        else:
            # Fall back to ROS_DISTRO env var confirmed by /opt/ros/<distro> on disk
            env_confirmed = _detect_distro_from_env()
            if env_confirmed:
                results.append(CheckResult(
                    checker_name="ROS 2 Distro",
                    status="pass",
                    message=(
                        f"ROS 2 '{env_confirmed}' confirmed via ROS_DISTRO + /opt/ros/"
                        f" (binary output did not include distro name)"
                    ),
                ))
                resolved_distro = env_confirmed
            elif env_distro:
                results.append(CheckResult(
                    checker_name="ROS 2 Distro",
                    status="warn",
                    message=(
                        f"ROS_DISTRO='{env_distro}' is set but /opt/ros/{env_distro} not found"
                    ),
                    fix=f"Install ROS 2 {env_distro} or correct ROS_DISTRO in ~/.bashrc",
                ))
                resolved_distro = None
            else:
                results.append(CheckResult(
                    checker_name="ROS 2 Distro",
                    status="warn",
                    message="Could not determine ROS 2 distro from binary or environment",
                    detail=f"Installed in /opt/ros: {opt_distros or 'none found'}",
                    fix="source /opt/ros/<distro>/setup.bash  # e.g. jazzy or humble",
                ))
                resolved_distro = None

        # 3. ROS_DISTRO env var consistency
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
        elif resolved_distro and env_distro != resolved_distro:
            results.append(CheckResult(
                checker_name="ROS_DISTRO env var",
                status="fail",
                message=f"ROS_DISTRO={env_distro!r} but detected distro is '{resolved_distro}' — mismatch!",
                fix=f"source /opt/ros/{resolved_distro}/setup.bash",
            ))
        else:
            results.append(CheckResult(
                checker_name="ROS_DISTRO env var",
                status="pass",
                message=f"ROS_DISTRO='{env_distro}' — matches binary",
            ))

        # 4. AMENT_PREFIX_PATH (confirms workspace was sourced)
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

        # 5. Matrix compatibility
        if self._matrix and resolved_distro:
            combos = self._matrix.get_combos()
            known_ros2 = {c["ros2"] for c in combos}
            if resolved_distro not in known_ros2:
                results.append(CheckResult(
                    checker_name="ROS 2 Compatibility",
                    status="warn",
                    message=(
                        f"ROS 2 '{resolved_distro}' is not listed in the compatibility matrix. "
                        f"Known distros: {sorted(known_ros2)}"
                    ),
                    fix="Use one of the tested ROS 2 distros: humble, jazzy",
                ))

        return results
