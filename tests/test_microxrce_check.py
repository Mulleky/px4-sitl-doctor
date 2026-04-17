"""Tests for MicroXRCEChecker."""

from __future__ import annotations

from unittest.mock import patch

from px4_doctor.checkers.microxrce_check import MicroXRCEChecker


def _make_checker(platform="ubuntu_22_04"):
    with patch("px4_doctor.checkers.microxrce_check.detect_platform", return_value=platform):
        return MicroXRCEChecker()


def test_skips_on_windows_native():
    checker = _make_checker("windows_native")
    results = checker.run()
    assert results[0].status == "skip"


def test_fail_when_binary_missing():
    checker = _make_checker()
    with patch("px4_doctor.checkers.microxrce_check.find_binary", return_value=None):
        results = checker.run()
    assert any(r.status == "fail" for r in results)
    fail = next(r for r in results if r.status == "fail")
    assert fail.fix is not None


def test_pass_with_valid_version():
    checker = _make_checker()
    with (
        patch("px4_doctor.checkers.microxrce_check.find_binary", return_value="/usr/bin/MicroXRCEAgent"),
        patch("px4_doctor.checkers.microxrce_check.run_cmd", return_value=(0, "MicroXRCEAgent v2.4.2\n", "")),
        patch("px4_doctor.checkers.microxrce_check._check_port_free", return_value=True),
    ):
        results = checker.run()
    version_result = next(r for r in results if "Version" in r.checker_name)
    assert version_result.status == "pass"


def test_fail_when_port_occupied():
    checker = _make_checker()
    with (
        patch("px4_doctor.checkers.microxrce_check.find_binary", return_value="/usr/bin/MicroXRCEAgent"),
        patch("px4_doctor.checkers.microxrce_check.run_cmd", return_value=(0, "version 2.4.2", "")),
        patch("px4_doctor.checkers.microxrce_check._check_port_free", return_value=False),
    ):
        results = checker.run()
    port_result = next(r for r in results if "Port" in r.checker_name)
    assert port_result.status == "fail"
    assert port_result.fix is not None
