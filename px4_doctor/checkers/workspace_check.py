"""ROS 2 workspace build state checker."""

from __future__ import annotations

import os
from pathlib import Path

from px4_doctor.checkers.base import BaseChecker
from px4_doctor.models.result import CheckResult
from px4_doctor.platform_utils import detect_platform, find_binary, get_home, run_cmd

_SKIP_PLATFORMS = {"windows_native", "macos"}

_COLCON_FIX = (
    "Install colcon:\n"
    "  pip install colcon-common-extensions\n"
    "Or: sudo apt install python3-colcon-common-extensions"
)

_WS_SEARCH = [
    "ros2_ws",
    "colcon_ws",
    "px4_ros_com_ros2",
]

_REQUIRED_PACKAGES = ["px4_msgs", "px4_ros_com"]


def _find_workspace(override: Path | None = None) -> Path | None:
    if override and override.exists():
        return override
    home = get_home()
    cwd = Path.cwd()
    for name in _WS_SEARCH:
        for base in (home, cwd):
            candidate = base / name
            if candidate.is_dir():
                return candidate
    if (cwd / "install").is_dir() and (cwd / "src").is_dir():
        return cwd
    return None


def _get_installed_ros2_packages() -> set[str]:
    """Return set of packages visible to `ros2 pkg list`, or empty set on failure."""
    ros2_bin = find_binary("ros2")
    if not ros2_bin:
        return set()
    rc, stdout, _ = run_cmd(["ros2", "pkg", "list"], timeout=10)
    if rc != 0:
        return set()
    return set(stdout.splitlines())


class WorkspaceChecker(BaseChecker):
    name = "ROS 2 Workspace"
    category = "workspace"
    platforms = ["ubuntu_22_04", "ubuntu_24_04", "ubuntu_other", "windows_wsl2"]

    def __init__(self, matrix=None, ws_path: str | None = None) -> None:
        self._matrix = matrix
        self._ws_override = Path(ws_path) if ws_path else None
        self._platform = detect_platform()

    def run(self) -> list[CheckResult]:
        if self._platform in _SKIP_PLATFORMS:
            return [self.skip(
                "ROS 2 workspace checks skipped on Windows native. Run inside WSL2."
            )]

        results: list[CheckResult] = []

        # 0. colcon must be installed to build any workspace
        colcon_bin = find_binary("colcon")
        if colcon_bin:
            results.append(CheckResult(
                checker_name="colcon",
                status="pass",
                message="colcon build tool found",
            ))
        else:
            results.append(CheckResult(
                checker_name="colcon",
                status="fail",
                message="colcon not found — required to build the ROS 2 workspace",
                fix=_COLCON_FIX,
            ))

        # 1. Find workspace
        ws = _find_workspace(self._ws_override)
        if ws is None:
            results.append(CheckResult(
                checker_name="ROS 2 Workspace",
                status="warn",
                message=(
                    "No ROS 2 workspace found in ~/ros2_ws, ~/colcon_ws, "
                    "~/px4_ros_com_ros2, or current directory"
                ),
                fix=(
                    "Create and build a workspace:\n"
                    "  mkdir -p ~/ros2_ws/src && cd ~/ros2_ws\n"
                    "  colcon build --symlink-install\n"
                    "Or pass --ws-path to specify the location."
                ),
            ))
            return results

        results.append(CheckResult(
            checker_name="ROS 2 Workspace",
            status="pass",
            message=f"Workspace found: {ws}",
        ))

        # 2. install/ directory — check before failing if packages are system-installed
        install_dir = ws / "install"
        if not install_dir.is_dir():
            installed_pkgs = _get_installed_ros2_packages()
            found = [p for p in _REQUIRED_PACKAGES if p in installed_pkgs]
            missing = [p for p in _REQUIRED_PACKAGES if p not in installed_pkgs]

            if found:
                results.append(CheckResult(
                    checker_name="Workspace Built",
                    status="warn",
                    message=(
                        f"Workspace not colcon-built (no install/), but "
                        f"{', '.join(found)} found in system ROS 2 environment — SITL may work"
                    ),
                    fix=(
                        f"cd {ws} && colcon build --symlink-install\n"
                        "(Recommended for full isolation; not required if using system packages)"
                    ),
                ))
                if missing:
                    for pkg in missing:
                        results.append(CheckResult(
                            checker_name=f"Package: {pkg}",
                            status="warn",
                            message=f"{pkg} not found in system ROS 2 or workspace",
                            fix=(
                                f"Clone and build {pkg}:\n"
                                f"  cd {ws}/src && git clone "
                                f"https://github.com/PX4/{pkg}.git\n"
                                f"  cd {ws} && colcon build --symlink-install"
                            ),
                        ))
            else:
                results.append(CheckResult(
                    checker_name="Workspace Built",
                    status="fail",
                    message="install/ directory missing — workspace has not been built",
                    fix=f"cd {ws} && colcon build --symlink-install",
                ))
            return results

        results.append(CheckResult(
            checker_name="Workspace Built",
            status="pass",
            message=f"install/ directory exists in {ws}",
        ))

        # 3. local_setup.bash sourced
        local_setup = install_dir / "local_setup.bash"
        if local_setup.exists():
            if os.environ.get("AMENT_PREFIX_PATH", ""):
                results.append(CheckResult(
                    checker_name="Workspace Sourced",
                    status="pass",
                    message="Workspace is sourced (AMENT_PREFIX_PATH set)",
                ))
            else:
                results.append(CheckResult(
                    checker_name="Workspace Sourced",
                    status="warn",
                    message="local_setup.bash exists but workspace does not appear to be sourced",
                    fix=(
                        f"source {local_setup}  # Add to ~/.bashrc:\n"
                        f"  echo 'source {local_setup}' >> ~/.bashrc"
                    ),
                ))
        else:
            results.append(CheckResult(
                checker_name="Workspace Sourced",
                status="warn",
                message="local_setup.bash not found — rebuild the workspace",
                fix=f"cd {ws} && colcon build --symlink-install",
            ))

        # 4. Required packages
        installed_pkgs = _get_installed_ros2_packages()
        if installed_pkgs:
            for pkg in _REQUIRED_PACKAGES:
                if pkg in installed_pkgs:
                    results.append(CheckResult(
                        checker_name=f"Package: {pkg}",
                        status="pass",
                        message=f"{pkg} is installed in the ROS 2 environment",
                    ))
                else:
                    results.append(CheckResult(
                        checker_name=f"Package: {pkg}",
                        status="fail",
                        message=f"{pkg} is NOT installed — required for PX4 ROS 2 communication",
                        fix=(
                            f"Clone and build {pkg}:\n"
                            f"  cd {ws}/src && git clone "
                            f"https://github.com/PX4/{pkg}.git\n"
                            f"  cd {ws} && colcon build --symlink-install"
                        ),
                    ))
        else:
            results.append(CheckResult(
                checker_name="Package Check",
                status="skip",
                message="ros2 binary not found — cannot check installed packages",
            ))

        return results
