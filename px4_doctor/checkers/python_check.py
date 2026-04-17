"""Python version and environment checker."""

from __future__ import annotations

import sys

from px4_doctor.checkers.base import BaseChecker
from px4_doctor.models.result import CheckResult
from px4_doctor.platform_utils import find_binary


class PythonChecker(BaseChecker):
    name = "Python Version"
    category = "core"
    platforms = ["all"]

    MIN_VERSION = (3, 10)

    def run(self) -> list[CheckResult]:
        results: list[CheckResult] = []

        # 1. Python version
        major, minor = sys.version_info.major, sys.version_info.minor
        version_str = f"{major}.{minor}.{sys.version_info.micro}"
        if (major, minor) >= self.MIN_VERSION:
            results.append(CheckResult(
                checker_name=self.name,
                status="pass",
                message=f"Python {version_str} — OK (>= 3.10 required)",
            ))
        else:
            results.append(CheckResult(
                checker_name=self.name,
                status="fail",
                message=f"Python {version_str} is too old — Python 3.10+ required",
                fix=(
                    "Install Python 3.10+:\n"
                    "  sudo apt install python3.10  # Ubuntu\n"
                    "  Or download from https://python.org"
                ),
            ))

        # 2. Virtual environment
        in_venv = sys.prefix != sys.base_prefix
        if in_venv:
            results.append(CheckResult(
                checker_name="Virtual Environment",
                status="pass",
                message=f"Virtual environment active: {sys.prefix}",
            ))
        else:
            results.append(CheckResult(
                checker_name="Virtual Environment",
                status="warn",
                message="No virtual environment active — system Python in use",
                fix=(
                    "Using a venv is recommended:\n"
                    "  python3 -m venv ~/.px4_venv && source ~/.px4_venv/bin/activate"
                ),
            ))

        # 3. pip available
        pip = find_binary("pip3") or find_binary("pip")
        if pip:
            results.append(CheckResult(
                checker_name="pip",
                status="pass",
                message=f"pip found: {pip}",
            ))
        else:
            results.append(CheckResult(
                checker_name="pip",
                status="warn",
                message="pip not found on PATH",
                fix="sudo apt install python3-pip  # or: python3 -m ensurepip",
            ))

        return results
