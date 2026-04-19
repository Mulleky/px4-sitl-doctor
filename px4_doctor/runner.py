"""Runner — orchestrates all checkers and aggregates results."""

from __future__ import annotations

import logging
import traceback
from dataclasses import dataclass, field

from px4_doctor.models.compat_matrix import CompatMatrix
from px4_doctor.models.result import CheckResult
from px4_doctor.platform_utils import detect_platform

logger = logging.getLogger(__name__)


@dataclass
class RunOptions:
    """Options passed from CLI to DoctorRunner."""

    px4_path: str | None = None
    ws_path: str | None = None
    offline: bool = False
    only: list[str] = field(default_factory=list)   # checker shortnames to run
    skip: list[str] = field(default_factory=list)   # checker shortnames to skip
    verbose: bool = False


# Maps CLI shortnames to checker class names
_CHECKER_SHORTNAMES: dict[str, str] = {
    "os": "OSChecker",
    "python": "PythonChecker",
    "ros2": "ROS2Checker",
    "gazebo": "GazeboChecker",
    "px4": "PX4Checker",
    "microxrce": "MicroXRCEChecker",
    "env": "EnvChecker",
    "library": "LibraryChecker",
    "port": "PortChecker",
    "workspace": "WorkspaceChecker",
    "network": "NetworkChecker",
    "wsl": "WSLChecker",
}


class RunReport:
    """Aggregated results from a full doctor run."""

    def __init__(self, results: list[CheckResult], platform: str) -> None:
        self.results = results
        self.platform = platform

    @property
    def pass_count(self) -> int:
        return sum(1 for r in self.results if r.status == "pass")

    @property
    def warn_count(self) -> int:
        return sum(1 for r in self.results if r.status == "warn")

    @property
    def fail_count(self) -> int:
        return sum(1 for r in self.results if r.status == "fail")

    @property
    def skip_count(self) -> int:
        return sum(1 for r in self.results if r.status == "skip")

    @property
    def has_failures(self) -> bool:
        return self.fail_count > 0

    @property
    def has_warnings(self) -> bool:
        return self.warn_count > 0

    @property
    def exit_code(self) -> int:
        """0 = all pass/skip, 1 = warnings only, 2 = any failures."""
        if self.has_failures:
            return 2
        if self.has_warnings:
            return 1
        return 0


class DoctorRunner:
    """Instantiates and runs all checkers, returning a RunReport."""

    def __init__(self, options: RunOptions | None = None) -> None:
        self._options = options or RunOptions()
        self._platform = detect_platform()
        self._matrix = CompatMatrix()

    def _build_checkers(self) -> list:
        """Instantiate all checkers, injecting shared context."""
        from px4_doctor.checkers.os_check import OSChecker
        from px4_doctor.checkers.python_check import PythonChecker
        from px4_doctor.checkers.ros2_check import ROS2Checker
        from px4_doctor.checkers.gazebo_check import GazeboChecker
        from px4_doctor.checkers.px4_check import PX4Checker
        from px4_doctor.checkers.microxrce_check import MicroXRCEChecker
        from px4_doctor.checkers.env_check import EnvChecker
        from px4_doctor.checkers.library_check import LibraryChecker
        from px4_doctor.checkers.port_check import PortChecker
        from px4_doctor.checkers.workspace_check import WorkspaceChecker
        from px4_doctor.checkers.network_check import NetworkChecker
        from px4_doctor.checkers.wsl_check import WSLChecker
        import os

        ros2_distro = os.environ.get("ROS_DISTRO", "")
        # We'll use the distro from env; gazebo name is unknown at this stage
        # — individual checkers will probe it themselves.

        all_checkers = [
            ("os",         OSChecker(matrix=self._matrix)),
            ("python",     PythonChecker()),
            ("ros2",       ROS2Checker(matrix=self._matrix)),
            ("gazebo",     GazeboChecker(matrix=self._matrix, ros2_distro=ros2_distro)),
            ("px4",        PX4Checker(
                               matrix=self._matrix,
                               px4_path=self._options.px4_path,
                               ros2_distro=ros2_distro,
                           )),
            ("microxrce",  MicroXRCEChecker(matrix=self._matrix, ros2_distro=ros2_distro)),
            ("env",        EnvChecker(matrix=self._matrix)),
            ("library",    LibraryChecker(matrix=self._matrix)),
            ("port",       PortChecker(matrix=self._matrix)),
            ("workspace",  WorkspaceChecker(matrix=self._matrix, ws_path=self._options.ws_path)),
            ("network",    NetworkChecker(offline=self._options.offline)),
            ("wsl",        WSLChecker(matrix=self._matrix)),
        ]

        # Filter by --only / --skip
        only = [s.lower() for s in self._options.only]
        skip = [s.lower() for s in self._options.skip]

        filtered = []
        for shortname, checker in all_checkers:
            if only and shortname not in only:
                continue
            if skip and shortname in skip:
                continue
            if not checker.applies_to(self._platform):
                continue
            filtered.append(checker)

        return filtered

    def run_all(self) -> RunReport:
        checkers = self._build_checkers()
        results: list[CheckResult] = []
        for checker in checkers:
            try:
                results.extend(checker.run())
            except Exception as exc:  # noqa: BLE001
                tb = traceback.format_exc()
                logger.debug("Checker %s raised: %s", checker.name, tb)
                results.append(CheckResult(
                    checker_name=checker.name,
                    status="fail",
                    message=f"Checker raised an unexpected error: {exc}",
                    detail=tb,
                ))
        return RunReport(results=results, platform=self._platform)
