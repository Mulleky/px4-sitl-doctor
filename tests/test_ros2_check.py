"""Tests for ROS2Checker."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from px4_doctor.checkers.ros2_check import ROS2Checker


def _make_checker(platform="ubuntu_22_04"):
    with patch("px4_doctor.checkers.ros2_check.detect_platform", return_value=platform):
        return ROS2Checker()


def test_skips_on_windows_native():
    checker = _make_checker("windows_native")
    results = checker.run()
    assert len(results) == 1
    assert results[0].status == "skip"


def test_fail_when_binary_missing():
    checker = _make_checker("ubuntu_22_04")
    with patch("px4_doctor.checkers.ros2_check.find_binary", return_value=None):
        results = checker.run()
    fail_results = [r for r in results if r.status == "fail"]
    assert fail_results, "Expected at least one fail when binary missing"
    assert fail_results[0].fix is not None


def test_pass_when_ros2_humble_detected(monkeypatch):
    checker = _make_checker("ubuntu_22_04")
    monkeypatch.setenv("ROS_DISTRO", "humble")
    monkeypatch.setenv("AMENT_PREFIX_PATH", "/opt/ros/humble")
    with (
        patch("px4_doctor.checkers.ros2_check.find_binary", return_value="/usr/bin/ros2"),
        patch("px4_doctor.checkers.ros2_check._detect_distro_from_binary", return_value="humble"),
        patch("px4_doctor.checkers.ros2_check._detect_distro_from_opt", return_value=["humble"]),
    ):
        results = checker.run()
    statuses = [r.status for r in results]
    assert "fail" not in statuses
    assert "pass" in statuses


def test_fail_on_ros_distro_mismatch(monkeypatch):
    checker = _make_checker("ubuntu_22_04")
    monkeypatch.setenv("ROS_DISTRO", "iron")
    monkeypatch.setenv("AMENT_PREFIX_PATH", "/opt/ros/humble")
    with (
        patch("px4_doctor.checkers.ros2_check.find_binary", return_value="/usr/bin/ros2"),
        patch("px4_doctor.checkers.ros2_check._detect_distro_from_binary", return_value="humble"),
        patch("px4_doctor.checkers.ros2_check._detect_distro_from_opt", return_value=["humble"]),
    ):
        results = checker.run()
    mismatch = [r for r in results if "mismatch" in r.message.lower() or "mismatch" in r.checker_name.lower()]
    fail_mismatch = [r for r in results if r.status == "fail" and "ROS_DISTRO" in r.checker_name]
    assert fail_mismatch, "Expected a fail for ROS_DISTRO mismatch"
    assert fail_mismatch[0].fix is not None
