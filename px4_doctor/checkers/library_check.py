"""Shared library presence checker."""

from __future__ import annotations

import os
from pathlib import Path

from px4_doctor.checkers.base import BaseChecker
from px4_doctor.models.result import CheckResult
from px4_doctor.platform_utils import detect_platform, run_cmd

_SKIP_PLATFORMS = {"windows_native", "macos"}


def _ldconfig_paths() -> set[Path]:
    """Return set of directories listed in ldconfig cache."""
    rc, stdout, stderr = run_cmd(["ldconfig", "-p"], timeout=5)
    paths: set[Path] = set()
    if rc != 0:
        return paths
    for line in stdout.splitlines():
        # Lines look like: "libfoo.so.1 (libc6,x86-64) => /usr/lib/libfoo.so.1"
        if "=>" in line:
            lib_path = line.split("=>")[-1].strip()
            paths.add(Path(lib_path).parent)
    return paths


def _expand_paths(raw_paths: list[str]) -> list[Path]:
    expanded = []
    for p in raw_paths:
        if p.startswith("~"):
            expanded.append(Path.home() / p[2:])
        else:
            expanded.append(Path(p))
    return expanded


class LibraryChecker(BaseChecker):
    name = "Shared Libraries"
    category = "core"
    platforms = ["ubuntu_22_04", "ubuntu_24_04", "ubuntu_other", "windows_wsl2"]

    def __init__(self, matrix=None) -> None:
        self._matrix = matrix
        self._platform = detect_platform()

    def run(self) -> list[CheckResult]:
        if self._platform in _SKIP_PLATFORMS:
            return [self.skip(
                "Shared library checks (.so) not applicable on Windows native. "
                "Run inside WSL2."
            )]

        results: list[CheckResult] = []

        if not self._matrix:
            return [self.skip("No compatibility matrix — skipping library checks.")]

        libs = self._matrix.get_required_libraries(self._platform)
        if not libs:
            results.append(CheckResult(
                checker_name=self.name,
                status="skip",
                message="No required libraries defined for this platform",
            ))
            return results

        # Build set of ldconfig search dirs (once)
        ldconfig_dirs = _ldconfig_paths()

        for lib_def in libs:
            lib_name = lib_def.get("name", "")
            description = lib_def.get("description", "")
            fix = lib_def.get("fix", "")
            raw_search = lib_def.get("search_paths", [])
            search_dirs = _expand_paths(raw_search) + list(ldconfig_dirs)

            found = any((d / lib_name).exists() for d in search_dirs)

            if found:
                results.append(CheckResult(
                    checker_name=lib_name,
                    status="pass",
                    message=f"{lib_name} found — {description}",
                ))
            else:
                results.append(CheckResult(
                    checker_name=lib_name,
                    status="warn",
                    message=f"{lib_name} not found — {description}",
                    fix=fix or None,
                    detail=f"Searched: {[str(d) for d in search_dirs[:5]]}",
                ))

        return results
