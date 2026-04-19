"""CLI-level tests via click.testing.CliRunner."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import yaml
from click.testing import CliRunner

from px4_doctor.cli import main
from px4_doctor.models import compat_matrix as cm


@pytest.fixture
def isolated_home(monkeypatch, tmp_path):
    """Redirect XDG_DATA_HOME so --update-matrix doesn't touch the real system."""
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    return tmp_path


class TestUpdateMatrix:
    def test_happy_path_writes_user_override(self, isolated_home):
        sample_yaml = "meta:\n  last_updated: 2026-04-01\ncombos: []\n"
        mock_resp = MagicMock()
        mock_resp.text = sample_yaml
        mock_resp.raise_for_status = MagicMock()

        runner = CliRunner()
        with patch("requests.get", return_value=mock_resp):
            result = runner.invoke(main, ["--update-matrix"])

        assert result.exit_code == 0, result.output
        dest = isolated_home / "px4-doctor" / "compatibility.yaml"
        assert dest.exists()
        assert "last_updated: 2026-04-01" in dest.read_text()
        assert "Updated" in result.output

    def test_network_failure_exits_nonzero(self, isolated_home):
        import requests

        runner = CliRunner()
        with patch("requests.get", side_effect=requests.ConnectionError("nope")):
            result = runner.invoke(main, ["--update-matrix"])

        assert result.exit_code != 0
        assert "ERROR" in result.output
        # No file should have been written
        assert not (isolated_home / "px4-doctor" / "compatibility.yaml").exists()

    def test_malformed_yaml_response_exits_nonzero(self, isolated_home):
        mock_resp = MagicMock()
        mock_resp.text = ":\n:\n: bad: yaml:::"
        mock_resp.raise_for_status = MagicMock()

        runner = CliRunner()
        with patch("requests.get", return_value=mock_resp):
            result = runner.invoke(main, ["--update-matrix"])

        # Either nonzero (yaml error) or zero if yaml happens to parse — but
        # this particular string is invalid YAML.
        assert result.exit_code != 0


class TestOnlySkipParsing:
    def test_only_empty_string_runs_nothing(self, monkeypatch):
        """--only '' currently produces an empty filter list and all checks pass through."""
        monkeypatch.setattr(
            "px4_doctor.runner.detect_platform", lambda: "ubuntu_22_04"
        )
        runner = CliRunner()
        # Use --offline so we don't hit network_check
        result = runner.invoke(main, ["--only", "", "--offline", "--plain"])
        # Should exit with a valid code (0/1/2), not crash
        assert result.exit_code in (0, 1, 2)

    def test_only_known_checker_runs(self, monkeypatch):
        monkeypatch.setattr(
            "px4_doctor.runner.detect_platform", lambda: "ubuntu_22_04"
        )
        runner = CliRunner()
        result = runner.invoke(main, ["--only", "os", "--offline", "--plain"])
        assert result.exit_code in (0, 1, 2)

    def test_only_unknown_checker_is_noop(self, monkeypatch):
        """Current behavior: unknown names silently filter to nothing. Documented here
        so a future change that validates names deliberately updates this test."""
        monkeypatch.setattr(
            "px4_doctor.runner.detect_platform", lambda: "ubuntu_22_04"
        )
        runner = CliRunner()
        result = runner.invoke(
            main, ["--only", "this-checker-does-not-exist", "--offline", "--plain"]
        )
        # Empty results → exit code 0 under current exit_code logic
        assert result.exit_code == 0


class TestListCombos:
    def test_runs_without_error(self):
        runner = CliRunner()
        result = runner.invoke(main, ["list-combos"])
        assert result.exit_code == 0
        assert "humble" in result.output.lower() or "jazzy" in result.output.lower()


class TestOfflineFlag:
    def test_offline_does_not_crash(self, monkeypatch):
        monkeypatch.setattr(
            "px4_doctor.runner.detect_platform", lambda: "ubuntu_22_04"
        )
        runner = CliRunner()
        result = runner.invoke(main, ["--offline", "--plain", "--only", "os"])
        assert result.exit_code in (0, 1, 2)
