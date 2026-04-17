"""Tests for CompatMatrix YAML loading and query methods."""

from __future__ import annotations

import pytest

from px4_doctor.models.compat_matrix import CompatMatrix


@pytest.fixture
def matrix():
    return CompatMatrix(offline=True)


def test_loads_combos(matrix):
    combos = matrix.get_combos()
    assert len(combos) >= 2, "Expected at least 2 combos"
    for combo in combos:
        assert "ros2" in combo
        assert "gazebo" in combo
        assert "px4_min" in combo


def test_loads_platforms(matrix):
    platforms = matrix.get_platform_ids()
    assert "ubuntu_22_04" in platforms
    assert "ubuntu_24_04" in platforms


def test_loads_required_ports(matrix):
    ports = matrix.get_required_ports()
    assert len(ports) >= 4
    port_numbers = {p["port"] for p in ports}
    assert 14540 in port_numbers
    assert 8888 in port_numbers


def test_ros2_gazebo_compatible(matrix):
    assert matrix.is_ros2_gazebo_compatible("humble", "harmonic")
    assert matrix.is_ros2_gazebo_compatible("jazzy", "harmonic")
    assert not matrix.is_ros2_gazebo_compatible("humble", "ionic")


def test_get_combo_for(matrix):
    combo = matrix.get_combo_for("humble", "harmonic")
    assert combo is not None
    assert combo["ros2"] == "humble"
    assert "px4_min" in combo


def test_get_required_env_vars_linux(matrix):
    env_vars = matrix.get_required_env_vars("ubuntu_22_04")
    names = [v["name"] for v in env_vars]
    assert "GZ_SIM_RESOURCE_PATH" in names
    assert "AMENT_PREFIX_PATH" in names


def test_get_required_env_vars_wsl2_includes_linux(matrix):
    env_vars = matrix.get_required_env_vars("windows_wsl2")
    names = [v["name"] for v in env_vars]
    assert "GZ_SIM_RESOURCE_PATH" in names
    assert "DISPLAY" in names


def test_get_required_libraries_linux(matrix):
    libs = matrix.get_required_libraries("ubuntu_22_04")
    assert len(libs) >= 1
    names = [l["name"] for l in libs]
    assert "libGstCameraSystem.so" in names


def test_version_comparison():
    """Ensure packaging version comparisons work correctly."""
    from packaging.version import Version
    assert Version("1.14.3") >= Version("1.14.0")
    assert Version("1.15.0") > Version("1.14.99")
    assert not (Version("1.13.0") >= Version("1.14.0"))
