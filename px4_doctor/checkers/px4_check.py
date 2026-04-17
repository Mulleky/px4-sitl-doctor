"""PX4-Autopilot repository detection and version checker."""

from __future__ import annotations

import re
from pathlib import Path

from px4_doctor.checkers.base import BaseChecker
from px4_doctor.models.result import CheckResult
from px4_doctor.platform_utils import detect_platform, get_home, parse_version, run_cmd

_SKIP_PLATFORMS = {"windows_native", "macos"}

_SEARCH_DIRS = [
    "PX4-Autopilot",
    "src/PX4-Autopilot",
]


def _find_px4_dir(override: Path | None = None) -> Path | None:
    """Return the first existing PX4-Autopilot directory, or None."""
    if override and override.exists():
        return override
    home = get_home()
    cwd = Path.cwd()
    for rel in _SEARCH_DIRS:
        for base in (home, cwd):
            candidate = base / rel
            if candidate.is_dir():
                return candidate
    return None


def _read_px4_version(px4_dir: Path) -> str | None:
    """Try to read PX4 version from version.h or git describe."""
    # Method 1: version.h
    version_h = px4_dir / "src" / "lib" / "version" / "version.h"
    if version_h.exists():
        try:
            content = version_h.read_text(encoding="utf-8", errors="replace")
            m = re.search(r'#define\s+PX4_GIT_VERSION_STR\s+"([^"]+)"', content)
            if m:
                return m.group(1)
        except OSError:
            pass

    # Method 2: git describe
    rc, stdout, stderr = run_cmd(
        ["git", "-C", str(px4_dir), "describe", "--tags", "--always"],
        timeout=8,
    )
    if rc == 0 and stdout.strip():
        return stdout.strip()

    return None


class PX4Checker(BaseChecker):
    name = "PX4 Autopilot"
    category = "core"
    platforms = ["ubuntu_22_04", "ubuntu_24_04", "ubuntu_other", "windows_wsl2"]

    def __init__(
        self,
        matrix=None,
        px4_path: str | None = None,
        ros2_distro: str | None = None,
        gazebo_name: str | None = None,
    ) -> None:
        self._matrix = matrix
        self._px4_path_override = Path(px4_path) if px4_path else None
        self._ros2_distro = ros2_distro or ""
        self._gazebo_name = gazebo_name or ""
        self._platform = detect_platform()

    def run(self) -> list[CheckResult]:
        if self._platform in _SKIP_PLATFORMS:
            return [self.skip(
                "PX4 checks skipped on Windows native. Run inside WSL2."
            )]

        results: list[CheckResult] = []

        # 1. Find PX4 directory
        px4_dir = _find_px4_dir(self._px4_path_override)
        if px4_dir is None:
            results.append(CheckResult(
                checker_name="PX4 Repository",
                status="fail",
                message=(
                    "PX4-Autopilot directory not found in ~/PX4-Autopilot, "
                    "~/src/PX4-Autopilot, or ./PX4-Autopilot"
                ),
                fix=(
                    "Clone PX4:\n"
                    "  git clone https://github.com/PX4/PX4-Autopilot.git "
                    "--recursive ~/PX4-Autopilot\n"
                    "Or pass --px4-path to specify the location."
                ),
            ))
            return results

        results.append(CheckResult(
            checker_name="PX4 Repository",
            status="pass",
            message=f"PX4-Autopilot found at {px4_dir}",
        ))

        # 2. Read version
        raw_version = _read_px4_version(px4_dir)
        parsed_version = parse_version(raw_version) if raw_version else None

        if parsed_version:
            results.append(CheckResult(
                checker_name="PX4 Version",
                status="pass",
                message=f"PX4 version: {parsed_version} (raw: {raw_version})",
            ))

            # 3. Check version against matrix
            if self._matrix and self._ros2_distro and self._gazebo_name:
                combo = self._matrix.get_combo_for(self._ros2_distro, self._gazebo_name)
                if combo:
                    from packaging.version import Version  # type: ignore[import-untyped]
                    px4_min = combo.get("px4_min")
                    px4_max = combo.get("px4_max")
                    ok = True
                    if px4_min and parsed_version < Version(px4_min):
                        ok = False
                        results.append(CheckResult(
                            checker_name="PX4 Version Compatibility",
                            status="fail",
                            message=(
                                f"PX4 {parsed_version} is older than minimum "
                                f"{px4_min} for {self._ros2_distro}+{self._gazebo_name}"
                            ),
                            fix=f"git -C {px4_dir} checkout v{px4_min}",
                        ))
                    if px4_max and parsed_version > Version(px4_max):
                        ok = False
                        results.append(CheckResult(
                            checker_name="PX4 Version Compatibility",
                            status="warn",
                            message=(
                                f"PX4 {parsed_version} exceeds tested maximum "
                                f"{px4_max} — may work but is untested"
                            ),
                        ))
                    if ok and px4_min:
                        results.append(CheckResult(
                            checker_name="PX4 Version Compatibility",
                            status="pass",
                            message=f"PX4 {parsed_version} is within the compatible range",
                        ))
        elif raw_version:
            results.append(CheckResult(
                checker_name="PX4 Version",
                status="warn",
                message=f"PX4 version string found but could not be parsed: {raw_version!r}",
            ))
        else:
            results.append(CheckResult(
                checker_name="PX4 Version",
                status="warn",
                message="Could not determine PX4 version (version.h not found and git failed)",
                fix=f"Ensure the repo is complete: git -C {px4_dir} submodule update --init",
            ))

        # 4. SITL build directory
        sitl_build = px4_dir / "build" / "px4_sitl_default"
        if sitl_build.is_dir():
            results.append(CheckResult(
                checker_name="PX4 SITL Build",
                status="pass",
                message=f"SITL build directory found: {sitl_build}",
            ))
        else:
            results.append(CheckResult(
                checker_name="PX4 SITL Build",
                status="warn",
                message=f"build/px4_sitl_default not found — simulation will fail if not built",
                fix=f"cd {px4_dir} && make px4_sitl gz_x500",
            ))

        return results
