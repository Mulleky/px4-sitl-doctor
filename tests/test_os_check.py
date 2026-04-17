"""Tests for OSChecker."""

from __future__ import annotations

import pytest
from unittest.mock import patch

from px4_doctor.checkers.os_check import OSChecker


def _run_with_platform(platform: str):
    with patch("px4_doctor.checkers.os_check.detect_platform", return_value=platform):
        checker = OSChecker()
        return checker.run()


def test_ubuntu_22_passes():
    results = _run_with_platform("ubuntu_22_04")
    assert len(results) == 1
    assert results[0].status == "pass"
    assert "22.04" in results[0].message


def test_ubuntu_24_passes():
    results = _run_with_platform("ubuntu_24_04")
    assert results[0].status == "pass"
    assert "24.04" in results[0].message


def test_ubuntu_other_warns():
    results = _run_with_platform("ubuntu_other")
    assert results[0].status == "warn"
    assert results[0].fix is not None


def test_wsl2_passes():
    results = _run_with_platform("windows_wsl2")
    assert results[0].status == "pass"


def test_windows_native_warns():
    results = _run_with_platform("windows_native")
    assert results[0].status == "warn"
    assert results[0].fix is not None


def test_unknown_fails():
    results = _run_with_platform("unknown")
    assert results[0].status == "fail"
    assert results[0].fix is not None
