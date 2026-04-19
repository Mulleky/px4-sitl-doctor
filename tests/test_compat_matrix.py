"""Tests for CompatMatrix YAML loading and query methods."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import yaml

from px4_doctor.models import compat_matrix as cm
from px4_doctor.models.compat_matrix import (
    CompatMatrix,
    _fetch_remote,
    _load_user_override,
    user_override_path,
)


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
    assert "AMENT_PREFIX_PATH" in names


def test_get_required_env_vars_wsl2_includes_linux(matrix):
    env_vars = matrix.get_required_env_vars("windows_wsl2")
    names = [v["name"] for v in env_vars]
    # WSL2 gets linux vars + wsl2-specific vars concatenated
    assert "AMENT_PREFIX_PATH" in names
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


class TestNoImplicitFetch:
    """Regression: default CompatMatrix() must not hit the network."""

    def test_default_constructor_does_not_fetch(self):
        with patch.object(cm, "_fetch_remote", side_effect=AssertionError("should not fetch")) as spy:
            CompatMatrix()
            assert spy.call_count == 0

    def test_offline_kw_is_accepted_and_ignored(self):
        """Backward compat: old callers pass offline=True; must still construct cleanly."""
        with patch.object(cm, "_fetch_remote", side_effect=AssertionError("should not fetch")):
            m = CompatMatrix(offline=True)
            assert m.get_combos()

    def test_fetch_remote_true_invokes_fetch(self):
        sample = {"combos": [], "platforms": [], "required_env_vars": {}}
        with patch.object(cm, "_fetch_remote", return_value=sample) as spy:
            CompatMatrix(fetch_remote=True)
            assert spy.call_count == 1

    def test_fetch_remote_failure_falls_back_to_bundled(self):
        with patch.object(cm, "_fetch_remote", return_value=None):
            m = CompatMatrix(fetch_remote=True)
            assert len(m.get_combos()) >= 1  # bundled content


class TestUserOverride:
    def test_override_path_respects_xdg(self, monkeypatch, tmp_path):
        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
        assert user_override_path() == tmp_path / "px4-doctor" / "compatibility.yaml"

    def test_override_path_default(self, monkeypatch, tmp_path):
        monkeypatch.delenv("XDG_DATA_HOME", raising=False)
        monkeypatch.setattr("px4_doctor.models.compat_matrix.Path.home", lambda: tmp_path)
        assert user_override_path() == tmp_path / ".local" / "share" / "px4-doctor" / "compatibility.yaml"

    def test_override_wins_over_bundled(self, monkeypatch, tmp_path):
        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
        override = tmp_path / "px4-doctor" / "compatibility.yaml"
        override.parent.mkdir(parents=True)
        override.write_text(
            "combos:\n  - {name: custom, ros2: humble, gazebo: harmonic, px4_min: '1.14.0'}\n"
            "platforms: []\nrequired_env_vars: {}\nrequired_binaries: {}\n"
            "required_libraries: {}\nrequired_ports: []\n"
        )
        m = CompatMatrix()
        combos = m.get_combos()
        assert len(combos) == 1
        assert combos[0]["name"] == "custom"

    def test_malformed_override_falls_back_to_bundled(self, monkeypatch, tmp_path):
        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
        override = tmp_path / "px4-doctor" / "compatibility.yaml"
        override.parent.mkdir(parents=True)
        override.write_text("::: not valid yaml :::")
        m = CompatMatrix()
        # Should silently fall back to bundled, which has multiple combos
        assert len(m.get_combos()) >= 1

    def test_missing_override_falls_back_to_bundled(self, monkeypatch, tmp_path):
        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
        m = CompatMatrix()
        assert len(m.get_combos()) >= 1


class TestFetchRemote:
    def test_http_error_returns_none(self):
        import requests
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = requests.HTTPError("404")
        with patch("requests.get", return_value=mock_resp):
            assert _fetch_remote() is None

    def test_timeout_returns_none(self):
        import requests
        with patch("requests.get", side_effect=requests.Timeout("slow")):
            assert _fetch_remote() is None

    def test_connection_error_returns_none(self):
        import requests
        with patch("requests.get", side_effect=requests.ConnectionError("no net")):
            assert _fetch_remote() is None

    def test_malformed_yaml_returns_none(self):
        mock_resp = MagicMock()
        mock_resp.text = "::: not yaml :::"
        mock_resp.raise_for_status = MagicMock()
        with patch("requests.get", return_value=mock_resp):
            assert _fetch_remote() is None

    def test_success_returns_parsed(self):
        mock_resp = MagicMock()
        mock_resp.text = "combos: []\n"
        mock_resp.raise_for_status = MagicMock()
        with patch("requests.get", return_value=mock_resp):
            assert _fetch_remote() == {"combos": []}


class TestQueryMethods:
    def test_unknown_platform_returns_empty_env_vars(self, matrix):
        assert matrix.get_required_env_vars("plan9") == []

    def test_unknown_platform_returns_empty_binaries(self, matrix):
        assert matrix.get_required_binaries("plan9") == []

    def test_get_fix_known_binary(self, matrix):
        # Not all bins have fixes, so just assert the lookup doesn't crash
        for entry in matrix.get_required_binaries("ubuntu_22_04"):
            name = entry.get("name")
            if name:
                result = matrix.get_fix(name, "ubuntu_22_04")
                assert result is None or isinstance(result, str)

    def test_get_fix_unknown_binary(self, matrix):
        assert matrix.get_fix("nonexistent-binary", "ubuntu_22_04") is None

    def test_ros2_gazebo_compat_is_case_insensitive(self, matrix):
        assert matrix.is_ros2_gazebo_compatible("HUMBLE", "Harmonic")
        assert matrix.is_ros2_gazebo_compatible("  jazzy  ", "HARMONIC")
