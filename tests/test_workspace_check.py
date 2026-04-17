"""Tests for WorkspaceChecker."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from px4_doctor.checkers.workspace_check import WorkspaceChecker
from px4_doctor.models.compat_matrix import CompatMatrix


def _make_checker(platform="ubuntu_22_04", ws_path=None):
    with patch("px4_doctor.checkers.workspace_check.detect_platform", return_value=platform):
        matrix = CompatMatrix(offline=True)
        return WorkspaceChecker(matrix=matrix, ws_path=ws_path)


def test_skips_on_windows_native():
    checker = _make_checker("windows_native")
    results = checker.run()
    assert results[0].status == "skip"


def test_warn_when_no_workspace_found():
    checker = _make_checker()
    with patch("px4_doctor.checkers.workspace_check._find_workspace", return_value=None):
        results = checker.run()
    assert any(r.status == "warn" for r in results)
    warn = next(r for r in results if r.status == "warn")
    assert warn.fix is not None


def test_fail_when_install_dir_missing(tmp_path):
    ws = tmp_path / "ros2_ws"
    ws.mkdir()
    # No install/ dir
    checker = _make_checker(ws_path=str(ws))
    with patch("px4_doctor.checkers.workspace_check._find_workspace", return_value=ws):
        results = checker.run()
    fail = next((r for r in results if r.status == "fail"), None)
    assert fail is not None
    assert fail.fix is not None


def test_pass_when_workspace_complete(tmp_path, monkeypatch):
    ws = tmp_path / "ros2_ws"
    install_dir = ws / "install"
    install_dir.mkdir(parents=True)
    (install_dir / "local_setup.bash").write_text("# setup")

    monkeypatch.setenv("AMENT_PREFIX_PATH", "/opt/ros/humble")

    checker = _make_checker(ws_path=str(ws))
    with (
        patch("px4_doctor.checkers.workspace_check._find_workspace", return_value=ws),
        patch("px4_doctor.checkers.workspace_check.find_binary", return_value="/usr/bin/ros2"),
        patch("px4_doctor.checkers.workspace_check.run_cmd",
              return_value=(0, "px4_msgs\npx4_ros_com\nstd_msgs\n", "")),
    ):
        results = checker.run()

    statuses = {r.checker_name: r.status for r in results}
    assert statuses.get("ROS 2 Workspace") == "pass"
    assert statuses.get("Workspace Built") == "pass"
    assert statuses.get("Package: px4_msgs") == "pass"
    assert statuses.get("Package: px4_ros_com") == "pass"
