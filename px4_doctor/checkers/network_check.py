"""Internet connectivity and reachability checker."""

from __future__ import annotations

from px4_doctor.checkers.base import BaseChecker
from px4_doctor.models.result import CheckResult

_TIMEOUT = 3  # seconds

_ENDPOINTS = [
    ("Internet (Cloudflare DNS)", "https://1.1.1.1", False),
    ("GitHub", "https://github.com", True),
    ("PyPI", "https://pypi.org", False),
]


class NetworkChecker(BaseChecker):
    name = "Network"
    category = "network"
    platforms = ["all"]

    def __init__(self, matrix=None, offline: bool = False) -> None:
        self._offline = offline

    def run(self) -> list[CheckResult]:
        if self._offline:
            return [self.skip("Network checks skipped (--offline flag passed).")]

        results: list[CheckResult] = []

        try:
            import requests  # type: ignore[import-untyped]
        except ImportError:
            return [CheckResult(
                checker_name=self.name,
                status="skip",
                message="'requests' package not installed — network checks skipped",
                fix="pip install requests",
            )]

        for label, url, critical in _ENDPOINTS:
            try:
                resp = requests.get(url, timeout=_TIMEOUT, allow_redirects=True)
                if resp.status_code < 500:
                    results.append(CheckResult(
                        checker_name=f"Network: {label}",
                        status="pass",
                        message=f"{label} reachable (HTTP {resp.status_code})",
                    ))
                else:
                    results.append(CheckResult(
                        checker_name=f"Network: {label}",
                        status="warn",
                        message=f"{label} returned HTTP {resp.status_code}",
                    ))
            except Exception as exc:  # noqa: BLE001
                results.append(CheckResult(
                    checker_name=f"Network: {label}",
                    status="warn",
                    message=f"{label} unreachable: {type(exc).__name__}",
                    detail=(
                        "Network connectivity is not required for local SITL, "
                        "but PX4 cloning and submodule fetching will fail."
                    ),
                ))

        return results
