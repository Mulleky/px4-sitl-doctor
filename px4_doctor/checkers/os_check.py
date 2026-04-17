"""OS version checker."""

from __future__ import annotations

from px4_doctor.checkers.base import BaseChecker
from px4_doctor.models.result import CheckResult
from px4_doctor.platform_utils import detect_platform


class OSChecker(BaseChecker):
    name = "OS Version"
    category = "core"
    platforms = ["all"]

    SUPPORTED = {
        "ubuntu_22_04": "Ubuntu 22.04 LTS (Jammy)",
        "ubuntu_24_04": "Ubuntu 24.04 LTS (Noble)",
        "windows_wsl2": "Windows WSL2 (Ubuntu guest)",
        "windows_native": "Windows native",
    }

    def __init__(self, matrix=None) -> None:
        self._matrix = matrix
        self._platform = detect_platform()

    def run(self) -> list[CheckResult]:
        results: list[CheckResult] = []
        plat = self._platform

        if plat in ("ubuntu_22_04", "ubuntu_24_04"):
            label = self.SUPPORTED[plat]
            results.append(CheckResult(
                checker_name=self.name,
                status="pass",
                message=f"{label} — supported",
            ))
        elif plat == "ubuntu_other":
            results.append(CheckResult(
                checker_name=self.name,
                status="warn",
                message="Ubuntu version not in tested set (22.04 / 24.04). Proceed with caution.",
                fix="Upgrade to Ubuntu 22.04 or 24.04 for full support.",
            ))
        elif plat == "windows_wsl2":
            results.append(CheckResult(
                checker_name=self.name,
                status="pass",
                message="Windows WSL2 detected — supported platform",
            ))
        elif plat == "windows_native":
            results.append(CheckResult(
                checker_name=self.name,
                status="warn",
                message=(
                    "Windows native Python detected. ROS 2, Gazebo, and PX4 "
                    "require WSL2 on Windows. ROS/Gazebo/PX4 checks will be skipped."
                ),
                fix=(
                    "Install WSL2: wsl --install\n"
                    "Then follow the PX4 WSL2 setup guide: "
                    "https://docs.px4.io/main/en/dev_setup/dev_env_windows_wsl.html"
                ),
            ))
        elif plat == "macos":
            results.append(CheckResult(
                checker_name=self.name,
                status="warn",
                message="macOS detected. PX4 SITL with Gazebo is only officially supported on Linux.",
                fix="Use Ubuntu 22.04 or 24.04 (bare metal or VM) for full SITL support.",
            ))
        else:
            results.append(CheckResult(
                checker_name=self.name,
                status="fail",
                message=f"Unrecognised platform: {plat}. Cannot validate environment.",
                fix="Use Ubuntu 22.04, Ubuntu 24.04, or Windows 10/11 with WSL2.",
            ))

        return results
