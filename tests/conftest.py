"""Shared pytest fixtures and mock helpers."""

from __future__ import annotations

import pytest


@pytest.fixture
def mock_platform_ubuntu_22(monkeypatch):
    """Patch detect_platform() to return ubuntu_22_04."""
    monkeypatch.setattr("px4_doctor.platform_utils.detect_platform", lambda: "ubuntu_22_04")
    return "ubuntu_22_04"


@pytest.fixture
def mock_platform_windows_native(monkeypatch):
    monkeypatch.setattr("px4_doctor.platform_utils.detect_platform", lambda: "windows_native")
    return "windows_native"


@pytest.fixture
def mock_platform_wsl2(monkeypatch):
    monkeypatch.setattr("px4_doctor.platform_utils.detect_platform", lambda: "windows_wsl2")
    return "windows_wsl2"


@pytest.fixture
def clean_env(monkeypatch):
    """Remove common ROS/Gazebo env vars so tests start clean."""
    for var in [
        "ROS_DISTRO", "AMENT_PREFIX_PATH", "GZ_SIM_RESOURCE_PATH",
        "GZ_SIM_SYSTEM_PLUGIN_PATH", "ROS_DOMAIN_ID", "DISPLAY",
    ]:
        monkeypatch.delenv(var, raising=False)
