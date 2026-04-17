"""Tests for PX4Checker."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from px4_doctor.checkers.px4_check import PX4Checker


def _make_checker(platform="ubuntu_22_04", **kwargs):
    with patch("px4_doctor.checkers.px4_check.detect_platform", return_value=platform):
        return PX4Checker(**kwargs)


def test_skips_on_windows_native():
    checker = _make_checker("windows_native")
    results = checker.run()
    assert results[0].status == "skip"


def test_fail_when_px4_not_found():
    checker = _make_checker()
    with patch("px4_doctor.checkers.px4_check._find_px4_dir", return_value=None):
        results = checker.run()
    assert any(r.status == "fail" for r in results)
    fail = next(r for r in results if r.status == "fail")
    assert fail.fix is not None


def test_pass_when_px4_found(tmp_path):
    px4_dir = tmp_path / "PX4-Autopilot"
    px4_dir.mkdir()
    # Simulate SITL build dir
    sitl_build = px4_dir / "build" / "px4_sitl_default"
    sitl_build.mkdir(parents=True)

    checker = _make_checker()
    with (
        patch("px4_doctor.checkers.px4_check._find_px4_dir", return_value=px4_dir),
        patch("px4_doctor.checkers.px4_check._read_px4_version", return_value="v1.14.3"),
    ):
        results = checker.run()

    repo_result = next(r for r in results if r.checker_name == "PX4 Repository")
    assert repo_result.status == "pass"
    build_result = next(r for r in results if r.checker_name == "PX4 SITL Build")
    assert build_result.status == "pass"


def test_warn_when_sitl_build_missing(tmp_path):
    px4_dir = tmp_path / "PX4-Autopilot"
    px4_dir.mkdir()
    checker = _make_checker()
    with (
        patch("px4_doctor.checkers.px4_check._find_px4_dir", return_value=px4_dir),
        patch("px4_doctor.checkers.px4_check._read_px4_version", return_value="v1.14.3"),
    ):
        results = checker.run()
    build_result = next(r for r in results if r.checker_name == "PX4 SITL Build")
    assert build_result.status == "warn"
    assert build_result.fix is not None
