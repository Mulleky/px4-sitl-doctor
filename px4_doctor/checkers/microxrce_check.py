"""MicroXRCEAgent binary and version checker."""

from __future__ import annotations

import re
import socket

from packaging.version import Version

from px4_doctor.checkers.base import BaseChecker
from px4_doctor.models.result import CheckResult
from px4_doctor.platform_utils import detect_platform, find_binary, parse_version, run_cmd

_SKIP_PLATFORMS = {"windows_native", "macos"}
_AGENT_PORT = 8888
_MIN_VERSION_FALLBACK = "2.4.0"


def _parse_microxrce_version(combined: str) -> Version | None:
    """Try to parse a semver string from MicroXRCEAgent output."""
    m = re.search(r"(\d+\.\d+\.\d+)", combined)
    if m:
        return parse_version(m.group(1))
    return None


def _detect_microxrce_version() -> tuple[Version | None, str]:
    """Try multiple invocations to extract a version. Returns (version, raw_output)."""
    for args in (["--version"], ["-v"], []):
        rc, stdout, stderr = run_cmd(["MicroXRCEAgent"] + args, timeout=4)
        combined = stdout + stderr
        ver = _parse_microxrce_version(combined)
        if ver is not None:
            return ver, combined
    # Collect last output for display
    _, stdout, stderr = run_cmd(["MicroXRCEAgent", "--version"], timeout=4)
    return None, (stdout + stderr)


class MicroXRCEChecker(BaseChecker):
    name = "MicroXRCEAgent"
    category = "core"
    platforms = ["ubuntu_22_04", "ubuntu_24_04", "ubuntu_other", "windows_wsl2"]

    def __init__(self, matrix=None, ros2_distro: str | None = None,
                 gazebo_name: str | None = None) -> None:
        self._matrix = matrix
        self._ros2_distro = ros2_distro or ""
        self._gazebo_name = gazebo_name or ""
        self._platform = detect_platform()

    def run(self) -> list[CheckResult]:
        if self._platform in _SKIP_PLATFORMS:
            return [self.skip(
                "MicroXRCEAgent checks skipped on Windows native. Run inside WSL2."
            )]

        results: list[CheckResult] = []

        # 1. Binary present?
        binary = find_binary("MicroXRCEAgent")
        if not binary:
            results.append(CheckResult(
                checker_name="MicroXRCEAgent Binary",
                status="fail",
                message="MicroXRCEAgent binary not found on PATH",
                fix=(
                    "Install Micro XRCE-DDS Agent:\n"
                    "  sudo snap install micro-xrce-dds-agent\n"
                    "Or build from source:\n"
                    "  https://micro-xrce-dds.docs.eprosima.com/en/latest/installation.html"
                ),
            ))
            return results

        # 2. Version — try multiple flags
        version, raw_output = _detect_microxrce_version()

        min_str = _MIN_VERSION_FALLBACK
        if self._matrix and self._ros2_distro and self._gazebo_name:
            combo = self._matrix.get_combo_for(self._ros2_distro, self._gazebo_name)
            if combo:
                min_str = combo.get("microxrce_min", _MIN_VERSION_FALLBACK)

        if version:
            # v3.x Agent is protocol-incompatible with PX4's embedded v2.x XRCE-DDS client.
            # Topics appear to connect but never show up in `ros2 topic list`.
            if version.major >= 3:
                results.append(CheckResult(
                    checker_name="MicroXRCEAgent Version",
                    status="warn",
                    message=(
                        f"MicroXRCEAgent {version} (v3.x) detected — "
                        "PX4's embedded XRCE-DDS client uses the v2.x protocol, "
                        "which is INCOMPATIBLE with Agent v3.x. "
                        "ROS 2 topics will not appear even if the agent starts."
                    ),
                    fix=(
                        "Downgrade to Agent v2.x:\n"
                        "  sudo snap install micro-xrce-dds-agent --channel=2.x/stable\n"
                        "Or build v2.4.3 from source:\n"
                        "  git clone https://github.com/eProsima/Micro-XRCE-DDS-Agent\n"
                        "  cd Micro-XRCE-DDS-Agent && git checkout v2.4.3\n"
                        "  mkdir build && cd build && cmake .. && make && sudo make install"
                    ),
                ))
            else:
                min_ver = parse_version(min_str)
                if min_ver and version >= min_ver:
                    results.append(CheckResult(
                        checker_name="MicroXRCEAgent Version",
                        status="pass",
                        message=f"MicroXRCEAgent {version} — OK (>= {min_str} required)",
                    ))
                elif min_ver:
                    results.append(CheckResult(
                        checker_name="MicroXRCEAgent Version",
                        status="fail",
                        message=f"MicroXRCEAgent {version} is older than minimum {min_str}",
                        fix=(
                            "Upgrade Micro XRCE-DDS Agent:\n"
                            "  sudo snap refresh micro-xrce-dds-agent\n"
                            "Or build latest from source."
                        ),
                    ))
        else:
            # Version not parseable — check raw output for signs of v3.x
            if "3." in raw_output or raw_output.strip().startswith("3"):
                results.append(CheckResult(
                    checker_name="MicroXRCEAgent Version",
                    status="warn",
                    message=(
                        "MicroXRCEAgent appears to be v3.x (version string not fully parsed). "
                        "PX4's embedded XRCE-DDS client uses v2.x — this combination is incompatible."
                    ),
                    fix=(
                        "Downgrade to Agent v2.x:\n"
                        "  sudo snap install micro-xrce-dds-agent --channel=2.x/stable"
                    ),
                    detail=f"Raw output: {raw_output[:120]}",
                ))
            else:
                results.append(CheckResult(
                    checker_name="MicroXRCEAgent Version",
                    status="pass",
                    message="MicroXRCEAgent found — version string format not recognized",
                    detail=f"Raw output: {raw_output[:120]}",
                ))

        # 3. Port 8888 availability
        if _check_port_free(_AGENT_PORT):
            results.append(CheckResult(
                checker_name="XRCE-DDS Port 8888",
                status="pass",
                message=f"UDP port {_AGENT_PORT} is available for MicroXRCEAgent",
            ))
        else:
            results.append(CheckResult(
                checker_name="XRCE-DDS Port 8888",
                status="fail",
                message=f"UDP port {_AGENT_PORT} is already in use — MicroXRCEAgent cannot start",
                fix=(
                    f"Find the process using the port:\n"
                    f"  sudo lsof -i UDP:{_AGENT_PORT}\n"
                    f"Kill it or change the agent port."
                ),
            ))

        return results


def _check_port_free(port: int) -> bool:
    """Return True if UDP port is available."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.bind(("0.0.0.0", port))
        return True
    except OSError:
        return False
    finally:
        sock.close()
