"""WSL2-specific environment checker."""

from __future__ import annotations

import os
from pathlib import Path

from px4_doctor.checkers.base import BaseChecker
from px4_doctor.models.result import CheckResult
from px4_doctor.platform_utils import detect_platform

_RUN_ON = {"windows_wsl2"}
_8GB_IN_KB = 8 * 1024 * 1024


class WSLChecker(BaseChecker):
    name = "WSL2 Environment"
    category = "core"
    platforms = ["windows_wsl2"]

    def __init__(self, matrix=None) -> None:
        self._platform = detect_platform()

    def run(self) -> list[CheckResult]:
        if self._platform not in _RUN_ON:
            return [self.skip("WSL2 checks only run on Windows WSL2 platform.")]

        results: list[CheckResult] = []

        # 1. Confirm WSL2 (not WSL1) from /proc/version
        proc_version = Path("/proc/version")
        wsl2_confirmed = False
        if proc_version.exists():
            try:
                content = proc_version.read_text(encoding="utf-8", errors="replace")
                if "wsl2" in content.lower() or ("microsoft" in content.lower() and "wsl2" in content.lower()):
                    wsl2_confirmed = True
                elif "microsoft" in content.lower():
                    # Could be WSL1
                    pass
                # Try reading /proc/sys/kernel/osrelease for "microsoft-standard-WSL2"
                osrelease = Path("/proc/sys/kernel/osrelease")
                if osrelease.exists():
                    osrel = osrelease.read_text(encoding="utf-8").strip()
                    if "wsl2" in osrel.lower() or "microsoft" in osrel.lower():
                        wsl2_confirmed = True
            except OSError:
                pass

        if wsl2_confirmed:
            results.append(CheckResult(
                checker_name="WSL2 Confirmed",
                status="pass",
                message="WSL2 kernel confirmed",
            ))
        else:
            results.append(CheckResult(
                checker_name="WSL2 Confirmed",
                status="fail",
                message="This appears to be WSL1, not WSL2. PX4 SITL requires WSL2 networking.",
                fix=(
                    "Upgrade to WSL2:\n"
                    "  wsl --set-version Ubuntu-22.04 2\n"
                    "Or create a new WSL2 instance:\n"
                    "  wsl --install -d Ubuntu-22.04"
                ),
            ))

        # 2. DISPLAY for X11/GUI
        display = os.environ.get("DISPLAY", "")
        if display:
            results.append(CheckResult(
                checker_name="DISPLAY (X11)",
                status="pass",
                message=f"DISPLAY={display!r} — X11 forwarding configured",
            ))
        else:
            results.append(CheckResult(
                checker_name="DISPLAY (X11)",
                status="warn",
                message="DISPLAY is not set — Gazebo GUI will not work",
                fix=(
                    "Add to ~/.bashrc in WSL2:\n"
                    "  export DISPLAY=$(cat /etc/resolv.conf | grep nameserver | awk '{print $2}'):0.0\n"
                    "Also install an X server on Windows (e.g. VcXsrv, Xming, or use WSLg)."
                ),
            ))

        # 3. systemd enabled
        proc1 = Path("/proc/1/cmdline")
        systemd_active = False
        if proc1.exists():
            try:
                cmdline = proc1.read_bytes().replace(b"\x00", b" ").decode("utf-8", errors="replace")
                if "systemd" in cmdline:
                    systemd_active = True
            except OSError:
                pass

        if systemd_active:
            results.append(CheckResult(
                checker_name="systemd",
                status="pass",
                message="systemd is running as PID 1 — ROS 2 daemons can start normally",
            ))
        else:
            results.append(CheckResult(
                checker_name="systemd",
                status="warn",
                message="systemd does not appear to be running — some ROS 2 daemons may not start",
                fix=(
                    "Enable systemd in WSL2 by adding to /etc/wsl.conf:\n"
                    "  [boot]\n"
                    "  systemd=true\n"
                    "Then restart WSL: wsl --shutdown"
                ),
            ))

        # 4. Memory check
        meminfo = Path("/proc/meminfo")
        if meminfo.exists():
            try:
                total_kb = 0
                for line in meminfo.read_text(encoding="utf-8").splitlines():
                    if line.startswith("MemTotal:"):
                        total_kb = int(line.split()[1])
                        break
                total_gb = total_kb / (1024 * 1024)
                if total_kb >= _8GB_IN_KB:
                    results.append(CheckResult(
                        checker_name="WSL2 Memory",
                        status="pass",
                        message=f"WSL2 memory: {total_gb:.1f} GB — OK (>= 8 GB recommended)",
                    ))
                else:
                    results.append(CheckResult(
                        checker_name="WSL2 Memory",
                        status="warn",
                        message=(
                            f"WSL2 memory: {total_gb:.1f} GB — "
                            "less than 8 GB recommended for PX4 + Gazebo"
                        ),
                        fix=(
                            "Increase WSL2 memory in %USERPROFILE%\\.wslconfig:\n"
                            "  [wsl2]\n"
                            "  memory=8GB\n"
                            "Then restart: wsl --shutdown"
                        ),
                    ))
            except (OSError, ValueError):
                pass

        return results
