"""Required environment variables checker."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from px4_doctor.checkers.base import BaseChecker
from px4_doctor.models.result import CheckResult
from px4_doctor.platform_utils import detect_platform


class EnvChecker(BaseChecker):
    name = "Environment Variables"
    category = "env"
    platforms = ["all"]

    def __init__(self, matrix=None) -> None:
        self._matrix = matrix
        self._platform = detect_platform()

    def run(self) -> list[CheckResult]:
        results: list[CheckResult] = []

        if not self._matrix:
            return [self.skip("No compatibility matrix loaded — skipping env checks.")]

        env_vars = self._matrix.get_required_env_vars(self._platform)

        if not env_vars:
            results.append(CheckResult(
                checker_name=self.name,
                status="skip",
                message=f"No required env vars defined for platform '{self._platform}'",
            ))
            return results

        for var_def in env_vars:
            name = var_def.get("name", "")
            description = var_def.get("description", "")
            required = var_def.get("required", True)
            check_path = var_def.get("check_path", False)
            fix = var_def.get("fix", "")

            value = os.environ.get(name, "")

            if not value:
                status = "fail" if required else "warn"
                results.append(CheckResult(
                    checker_name=name,
                    status=status,
                    message=f"{name} is not set — {description}",
                    fix=fix or None,
                ))
            else:
                # Variable is set; optionally verify the path exists
                if check_path:
                    # Handle path-separated lists: ":" on Linux, ";" on Windows
                    sep = ";" if sys.platform == "win32" else ":"
                    first_path = value.split(sep)[0]
                    if Path(first_path).exists():
                        results.append(CheckResult(
                            checker_name=name,
                            status="pass",
                            message=f"{name}={value[:60]} — set and path exists",
                        ))
                    else:
                        results.append(CheckResult(
                            checker_name=name,
                            status="warn",
                            message=f"{name} is set but path does not exist: {first_path}",
                            fix=fix or f"Verify {name} points to an existing directory",
                        ))
                else:
                    results.append(CheckResult(
                        checker_name=name,
                        status="pass",
                        message=f"{name} is set",
                    ))

        return results
