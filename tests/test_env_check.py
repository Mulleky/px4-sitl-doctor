"""Tests for EnvChecker."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from px4_doctor.checkers.env_check import EnvChecker
from px4_doctor.models.compat_matrix import CompatMatrix


def _make_checker(platform="ubuntu_22_04", matrix=None):
    with patch("px4_doctor.checkers.env_check.detect_platform", return_value=platform):
        if matrix is None:
            matrix = CompatMatrix(offline=True)
        return EnvChecker(matrix=matrix)


def test_fails_when_required_var_missing(monkeypatch):
    monkeypatch.delenv("GZ_SIM_RESOURCE_PATH", raising=False)
    monkeypatch.delenv("GZ_SIM_SYSTEM_PLUGIN_PATH", raising=False)
    monkeypatch.delenv("AMENT_PREFIX_PATH", raising=False)

    checker = _make_checker()
    results = checker.run()
    fail_results = [r for r in results if r.status == "fail"]
    assert fail_results, "Expected failures for missing required env vars"
    for r in fail_results:
        assert r.fix is not None


def test_passes_when_vars_set(monkeypatch, tmp_path):
    # GZ_SIM_RESOURCE_PATH is a path-checked var — point to tmp_path so it exists
    monkeypatch.setenv("GZ_SIM_RESOURCE_PATH", str(tmp_path))
    monkeypatch.setenv("GZ_SIM_SYSTEM_PLUGIN_PATH", "/some/path")
    monkeypatch.setenv("AMENT_PREFIX_PATH", "/opt/ros/humble")

    checker = _make_checker()
    results = checker.run()
    gz_resource = next((r for r in results if r.checker_name == "GZ_SIM_RESOURCE_PATH"), None)
    assert gz_resource is not None
    assert gz_resource.status == "pass"


def test_skips_when_no_matrix():
    with patch("px4_doctor.checkers.env_check.detect_platform", return_value="ubuntu_22_04"):
        checker = EnvChecker(matrix=None)
        results = checker.run()
    assert results[0].status == "skip"
