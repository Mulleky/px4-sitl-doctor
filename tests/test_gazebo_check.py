"""Tests for GazeboChecker."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from px4_doctor.checkers.gazebo_check import GazeboChecker


def _make_checker(platform="ubuntu_22_04", **kwargs):
    with patch("px4_doctor.checkers.gazebo_check.detect_platform", return_value=platform):
        return GazeboChecker(**kwargs)


def test_skips_on_windows_native():
    checker = _make_checker("windows_native")
    results = checker.run()
    assert results[0].status == "skip"


def test_fail_when_binary_missing():
    checker = _make_checker()
    with patch("px4_doctor.checkers.gazebo_check._detect_gazebo", return_value=(None, None)):
        results = checker.run()
    assert any(r.status == "fail" for r in results)
    fail = next(r for r in results if r.status == "fail")
    assert fail.fix is not None


def test_pass_with_harmonic(monkeypatch):
    from packaging.version import Version
    checker = _make_checker(ros2_distro="humble")
    monkeypatch.delenv("GZ_SIM_RESOURCE_PATH", raising=False)
    monkeypatch.delenv("GZ_SIM_SYSTEM_PLUGIN_PATH", raising=False)
    with patch("px4_doctor.checkers.gazebo_check._detect_gazebo",
               return_value=("gz", Version("8.6.0"))):
        results = checker.run()
    binary_result = next(r for r in results if r.checker_name == "Gazebo Binary")
    assert binary_result.status == "pass"
    assert "harmonic" in binary_result.message.lower()
