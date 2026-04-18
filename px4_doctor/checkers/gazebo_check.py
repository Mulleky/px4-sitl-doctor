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
_MAJOR_TO_NAME = {6: "fortress", 7: "garden", 8: "harmonic", 9: "ionic", 10: "jetty"}
_NAME_TO_MAJOR = {v: k for k, v in _MAJOR_TO_NAME.items()}


def _detect_gazebo() -> tuple[str | None, object | None, str | None]:
    """Return (binary, parsed_version, codename) — version/codename may be None."""
    for binary in ("gz", "ign"):
        if not find_binary(binary):
            continue

        # Try `gz --version` first
        rc, stdout, stderr = run_cmd([binary, "--version"])
        combined = (stdout + stderr).lower()

        m = re.search(r"(\d+\.\d+\.\d+)", combined)
        if m:
            ver = parse_version(m.group(1))
            codename = _MAJOR_TO_NAME.get(ver.major) if ver else None
            return binary, ver, codename

        # Try `gz sim --version` (newer gz splits subcommands)
        rc2, stdout2, stderr2 = run_cmd([binary, "sim", "--version"])
        combined2 = (stdout2 + stderr2).lower()
        m2 = re.search(r"(\d+\.\d+\.\d+)", combined2)
        if m2:
            ver = parse_version(m2.group(1))
            codename = _MAJOR_TO_NAME.get(ver.major) if ver else None
            return binary, ver, codename

        # Fall back: detect codename from text (e.g. "Gazebo Harmonic")
        for name, major in _NAME_TO_MAJOR.items():
            if name in combined or name in combined2:
                return binary, None, name

        # Binary found but nothing parseable
        return binary, None, None

    return None, None, None


def _scan_bashrc(var_name: str) -> bool:
    """Return True if 'export VAR_NAME=' appears in ~/.bashrc."""
    bashrc = Path.home() / ".bashrc"
    if not bashrc.exists():
        return False
    try:
        for line in bashrc.read_text(encoding="utf-8", errors="replace").splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if f"export {var_name}=" in stripped or f"export {var_name} " in stripped:
                return True
    except OSError:
        pass
    return False


def _check_gz_env(var_name: str, default_path: Path) -> CheckResult:
    """Two-tier check for a GZ_SIM env var.

    Tier 1: var set in current shell — validate paths exist.
    Tier 2: var not set — check ~/.bashrc, then check default path on disk.
    """
    value = os.environ.get(var_name, "")

    if value:
        # Tier 1: set in shell — verify at least one path exists
        paths = [Path(p) for p in value.split(":") if p]
        existing = [p for p in paths if p.exists()]
        if existing:
            return CheckResult(
                checker_name=var_name,
                status="pass",
                message=f"{var_name} set and path exists",
                detail=value[:80],
            )
        return CheckResult(
            checker_name=var_name,
            status="warn",
            message=f"{var_name} is set but none of the paths exist: {value[:60]}",
            fix="Build PX4 first or correct the path in ~/.bashrc",
        )

    # Tier 2: not in current shell
    if _scan_bashrc(var_name):
        return CheckResult(
            checker_name=var_name,
            status="warn",
            message=f"{var_name} is in ~/.bashrc but not active — restart your terminal",
            fix=f"Run: source ~/.bashrc",
        )

    if default_path.exists():
        return CheckResult(
            checker_name=var_name,
            status="warn",
            message=(
                f"{var_name} not set in this shell, but default path found at {default_path}"
            ),
            fix=(
                f"Add to ~/.bashrc to make it permanent:\n"
                f"  export {var_name}={default_path}"
            ),
        )

    return CheckResult(
        checker_name=var_name,
        status="fail",
        message=f"{var_name} is not set and default path not found",
        fix=(
            f"Build PX4 first, then add to ~/.bashrc:\n"
            f"  export {var_name}={default_path}"
        ),
    )


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

        # 1. Binary + version
        binary, version, codename = _detect_gazebo()
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

        if version is not None:
            label = f"gz {version} ({codename})" if codename else f"gz {version}"
            results.append(CheckResult(
                checker_name="Gazebo Binary",
                status="pass",
                message=f"{label} found",
                detail=f"Binary: {binary}",
            ))
        elif codename is not None:
            results.append(CheckResult(
                checker_name="Gazebo Binary",
                status="pass",
                message=f"Gazebo {codename.title()} found (semver not parseable)",
                detail=f"Binary: {binary}",
            ))
        else:
            results.append(CheckResult(
                checker_name="Gazebo Binary",
                status="warn",
                message=f"'{binary}' found but version could not be determined",
                fix="Ensure Gazebo is correctly installed: sudo apt install gz-harmonic",
            ))

        # 2. ROS 2 + Gazebo compatibility
        if self._matrix and self._ros2_distro and codename:
            if self._matrix.is_ros2_gazebo_compatible(self._ros2_distro, codename):
                results.append(CheckResult(
                    checker_name="ROS2 + Gazebo Combo",
                    status="pass",
                    message=f"{self._ros2_distro} + {codename} — compatible combo found in matrix",
                ))
            else:
                results.append(CheckResult(
                    checker_name="ROS2 + Gazebo Combo",
                    status="fail",
                    message=f"{self._ros2_distro} + {codename} is NOT a known-compatible combination",
                    fix=(
                        "Supported combos:\n"
                        "  ROS 2 Humble  + Gazebo Harmonic (Ubuntu 22.04/24.04)\n"
                        "  ROS 2 Jazzy   + Gazebo Harmonic (Ubuntu 24.04)\n"
                        "  ROS 2 Jazzy   + Gazebo Ionic    (Ubuntu 24.04)"
                    ),
                ))

        # 3. GZ_SIM_RESOURCE_PATH (two-tier)
        default_resource = Path.home() / "PX4-Autopilot" / "Tools" / "simulation" / "gz" / "models"
        results.append(_check_gz_env("GZ_SIM_RESOURCE_PATH", default_resource))

        # 4. GZ_SIM_SYSTEM_PLUGIN_PATH (two-tier)
        default_plugin = Path.home() / "PX4-Autopilot" / "build" / "px4_sitl_default" / "lib"
        results.append(_check_gz_env("GZ_SIM_SYSTEM_PLUGIN_PATH", default_plugin))

        # 5. Camera plugin
        camera_lib = "libGstCameraSystem.so"
        plugin_path = os.environ.get("GZ_SIM_SYSTEM_PLUGIN_PATH", "")
        search_dirs = [
            Path.home() / ".gz" / "sim" / "plugins",
            Path.home() / "PX4-Autopilot" / "build" / "px4_sitl_default" / "lib",
        ]
        if plugin_path:
            for p in plugin_path.split(":"):
                search_dirs.append(Path(p))

        if any((d / camera_lib).exists() for d in search_dirs):
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
