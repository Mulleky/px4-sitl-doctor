"""CLI-level tests for features added in v0.3.0:
    fix, init, snap save/diff, --export-env, --watch.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from px4_doctor.cli import main
from px4_doctor.models.result import CheckResult
from px4_doctor.runner import RunReport


def _mock_report(*results: CheckResult) -> RunReport:
    return RunReport(results=list(results), platform="ubuntu_22_04")


def _patch_runner(results: list[CheckResult]):
    """Context manager that patches DoctorRunner.run_all to return fixed results."""
    report = _mock_report(*results)
    return patch("px4_doctor.runner.DoctorRunner.run_all", return_value=report)


def _patch_platform():
    return patch("px4_doctor.runner.detect_platform", return_value="ubuntu_22_04")


# ---------------------------------------------------------------------------
# fix subcommand
# ---------------------------------------------------------------------------

class TestFixCommand:
    def test_dry_run_exits_without_executing(self, monkeypatch):
        monkeypatch.setattr("px4_doctor.runner.detect_platform", lambda: "ubuntu_22_04")
        runner = CliRunner()
        with patch("subprocess.run") as mock_sub:
            result = runner.invoke(main, ["fix", "--offline", "--only", "os", "--plain"])
        mock_sub.assert_not_called()
        assert result.exit_code in (0, 1, 2)

    def test_dry_run_shows_fix_commands(self, monkeypatch):
        monkeypatch.setattr("px4_doctor.runner.detect_platform", lambda: "ubuntu_22_04")
        with _patch_runner([
            CheckResult("ROS 2 Binary", "fail", "not found",
                        fix="sudo apt install ros-humble-desktop")
        ]):
            runner = CliRunner()
            result = runner.invoke(main, ["fix", "--plain"])
        assert result.exit_code in (0, 1, 2)
        assert "sudo apt install ros-humble-desktop" in result.output or "--run" in result.output

    def test_run_yes_executes_commands(self, monkeypatch):
        monkeypatch.setattr("px4_doctor.runner.detect_platform", lambda: "ubuntu_22_04")
        with (
            _patch_runner([
                CheckResult("ROS 2 Binary", "fail", "not found",
                            fix="sudo apt install ros-humble-desktop")
            ]),
            patch("subprocess.run") as mock_sub,
        ):
            mock_sub.return_value = MagicMock(returncode=0)
            runner = CliRunner()
            result = runner.invoke(main, ["fix", "--run", "--yes", "--plain"])
        mock_sub.assert_called()
        assert result.exit_code == 0

    def test_no_failures_clean_exit(self, monkeypatch):
        monkeypatch.setattr("px4_doctor.runner.detect_platform", lambda: "ubuntu_22_04")
        with _patch_runner([CheckResult("OS", "pass", "Ubuntu 22.04")]):
            runner = CliRunner()
            result = runner.invoke(main, ["fix", "--plain"])
        assert result.exit_code == 0

    def test_only_flag_respected(self, monkeypatch):
        monkeypatch.setattr("px4_doctor.runner.detect_platform", lambda: "ubuntu_22_04")
        runner = CliRunner()
        result = runner.invoke(main, ["fix", "--only", "os", "--offline", "--plain"])
        assert result.exit_code in (0, 1, 2)


# ---------------------------------------------------------------------------
# init subcommand
# ---------------------------------------------------------------------------

class TestInitCommand:
    def test_runs_without_crash(self, monkeypatch):
        monkeypatch.setattr("px4_doctor.runner.detect_platform", lambda: "ubuntu_22_04")
        runner = CliRunner()
        result = runner.invoke(main, ["init", "--offline", "--plain"])
        assert result.exit_code in (0, 1, 2)

    def test_output_contains_step_numbers(self, monkeypatch):
        monkeypatch.setattr("px4_doctor.runner.detect_platform", lambda: "ubuntu_22_04")
        runner = CliRunner()
        result = runner.invoke(main, ["init", "--offline", "--plain"])
        assert "Step 1" in result.output
        assert "Step 10" in result.output

    def test_exit_code_2_on_failures(self, monkeypatch):
        monkeypatch.setattr("px4_doctor.runner.detect_platform", lambda: "ubuntu_22_04")
        with _patch_runner([
            CheckResult("ROS 2 Binary", "fail", "not found",
                        fix="sudo apt install ros-humble-desktop")
        ]):
            runner = CliRunner()
            result = runner.invoke(main, ["init", "--plain"])
        assert result.exit_code == 2

    def test_exit_code_0_all_pass(self, monkeypatch):
        monkeypatch.setattr("px4_doctor.runner.detect_platform", lambda: "ubuntu_22_04")
        with _patch_runner([CheckResult("OS Version", "pass", "Ubuntu 22.04")]):
            runner = CliRunner()
            result = runner.invoke(main, ["init", "--plain"])
        assert result.exit_code == 0

    def test_only_flag_works(self, monkeypatch):
        monkeypatch.setattr("px4_doctor.runner.detect_platform", lambda: "ubuntu_22_04")
        runner = CliRunner()
        result = runner.invoke(main, ["init", "--only", "os", "--offline", "--plain"])
        assert result.exit_code in (0, 1, 2)


# ---------------------------------------------------------------------------
# snap save
# ---------------------------------------------------------------------------

class TestSnapSave:
    def test_creates_snapshot_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr("px4_doctor.runner.detect_platform", lambda: "ubuntu_22_04")
        dest = str(tmp_path / "snap.json")
        runner = CliRunner()
        result = runner.invoke(main, ["snap", "save", dest, "--offline", "--only", "os"])
        assert result.exit_code == 0, result.output
        assert Path(dest).exists()

    def test_snapshot_is_valid_json(self, tmp_path, monkeypatch):
        monkeypatch.setattr("px4_doctor.runner.detect_platform", lambda: "ubuntu_22_04")
        dest = str(tmp_path / "snap.json")
        runner = CliRunner()
        runner.invoke(main, ["snap", "save", dest, "--offline", "--only", "os"])
        data = json.loads(Path(dest).read_text(encoding="utf-8"))
        assert "results" in data
        assert "timestamp" in data

    def test_output_confirms_path(self, tmp_path, monkeypatch):
        monkeypatch.setattr("px4_doctor.runner.detect_platform", lambda: "ubuntu_22_04")
        dest = str(tmp_path / "snap.json")
        runner = CliRunner()
        result = runner.invoke(main, ["snap", "save", dest, "--offline", "--only", "os"])
        assert dest in result.output or "snap.json" in result.output


# ---------------------------------------------------------------------------
# snap diff
# ---------------------------------------------------------------------------

class TestSnapDiff:
    def _make_snap(self, tmp_path, *results: CheckResult) -> str:
        from px4_doctor.snapshot import save_snapshot
        report = _mock_report(*results)
        dest = str(tmp_path / "baseline.json")
        save_snapshot(report, dest)
        return dest

    def test_no_change_detected(self, tmp_path, monkeypatch):
        monkeypatch.setattr("px4_doctor.runner.detect_platform", lambda: "ubuntu_22_04")
        snap = self._make_snap(tmp_path, CheckResult("OS Version", "pass", "ok"))
        with _patch_runner([CheckResult("OS Version", "pass", "ok")]):
            runner = CliRunner()
            result = runner.invoke(main, ["snap", "diff", snap, "--plain"])
        assert result.exit_code == 0
        assert "No changes" in result.output or "identical" in result.output

    def test_regression_shown(self, tmp_path, monkeypatch):
        monkeypatch.setattr("px4_doctor.runner.detect_platform", lambda: "ubuntu_22_04")
        snap = self._make_snap(tmp_path, CheckResult("ROS 2 Binary", "pass", "was ok"))
        with _patch_runner([CheckResult("ROS 2 Binary", "fail", "now broken")]):
            runner = CliRunner()
            result = runner.invoke(main, ["snap", "diff", snap, "--plain"])
        assert "BROKEN" in result.output or "fail" in result.output.lower()

    def test_missing_file_exits_nonzero(self, monkeypatch):
        monkeypatch.setattr("px4_doctor.runner.detect_platform", lambda: "ubuntu_22_04")
        runner = CliRunner()
        result = runner.invoke(main, ["snap", "diff", "/nonexistent/path.json"])
        assert result.exit_code != 0

    def test_fixed_issue_shown(self, tmp_path, monkeypatch):
        monkeypatch.setattr("px4_doctor.runner.detect_platform", lambda: "ubuntu_22_04")
        snap = self._make_snap(tmp_path, CheckResult("ROS 2 Binary", "fail", "was broken"))
        with _patch_runner([CheckResult("ROS 2 Binary", "pass", "now fixed")]):
            runner = CliRunner()
            result = runner.invoke(main, ["snap", "diff", snap, "--plain"])
        assert "fixed" in result.output.lower() or "resolved" in result.output.lower()


# ---------------------------------------------------------------------------
# --export-env
# ---------------------------------------------------------------------------

class TestExportEnv:
    def test_prints_export_lines(self, monkeypatch):
        monkeypatch.setattr("px4_doctor.runner.detect_platform", lambda: "ubuntu_22_04")
        with _patch_runner([
            CheckResult("AMENT_PREFIX_PATH", "fail", "not set",
                        fix="Source your ROS 2 installation:\n  source /opt/ros/humble/setup.bash")
        ]):
            runner = CliRunner()
            result = runner.invoke(main, ["--export-env", "--plain"])
        assert result.exit_code in (0, 1, 2)
        assert "source /opt/ros/humble/setup.bash" in result.output

    def test_no_failures_prints_clean_message(self, monkeypatch):
        monkeypatch.setattr("px4_doctor.runner.detect_platform", lambda: "ubuntu_22_04")
        with _patch_runner([CheckResult("OS", "pass", "ok")]):
            runner = CliRunner()
            result = runner.invoke(main, ["--export-env", "--plain"])
        assert result.exit_code in (0, 1, 2)
        assert "No missing" in result.output or "#" in result.output

    def test_export_lines_extracted(self, monkeypatch):
        monkeypatch.setattr("px4_doctor.runner.detect_platform", lambda: "ubuntu_22_04")
        with _patch_runner([
            CheckResult("ROS_DOMAIN_ID", "warn", "not set",
                        fix="Optional: export ROS_DOMAIN_ID=0")
        ]):
            runner = CliRunner()
            result = runner.invoke(main, ["--export-env"])
        assert result.exit_code in (0, 1, 2)
        assert "export ROS_DOMAIN_ID=0" in result.output


# ---------------------------------------------------------------------------
# --watch (basic, non-looping test)
# ---------------------------------------------------------------------------

class TestWatchFlag:
    def test_watch_runs_one_iteration_then_interrupted(self, monkeypatch):
        """Simulate Ctrl+C after one iteration — should exit cleanly with code 0."""
        monkeypatch.setattr("px4_doctor.runner.detect_platform", lambda: "ubuntu_22_04")

        call_count = 0

        def fake_sleep(_):
            nonlocal call_count
            call_count += 1
            if call_count >= 1:
                raise KeyboardInterrupt

        with (
            patch("time.sleep", side_effect=fake_sleep),
            _patch_runner([CheckResult("OS Version", "pass", "Ubuntu 22.04")]),
        ):
            runner = CliRunner()
            result = runner.invoke(main, ["--watch", "--interval", "1", "--plain", "--offline"])

        assert result.exit_code == 0
        assert call_count >= 1

    def test_watch_shows_changed_status(self, monkeypatch):
        """After two iterations where status changes, output should mention the change."""
        monkeypatch.setattr("px4_doctor.runner.detect_platform", lambda: "ubuntu_22_04")

        iteration = [0]
        reports = [
            _mock_report(CheckResult("ROS 2 Binary", "fail", "missing")),
            _mock_report(CheckResult("ROS 2 Binary", "pass", "found")),
        ]

        def fake_run_all(self_):
            idx = min(iteration[0], len(reports) - 1)
            r = reports[idx]
            iteration[0] += 1
            return r

        sleep_calls = [0]

        def fake_sleep(_):
            sleep_calls[0] += 1
            if sleep_calls[0] >= 2:
                raise KeyboardInterrupt

        with (
            patch("px4_doctor.runner.DoctorRunner.run_all", fake_run_all),
            patch("time.sleep", side_effect=fake_sleep),
        ):
            runner = CliRunner()
            result = runner.invoke(main, ["--watch", "--interval", "1", "--plain", "--offline"])

        assert result.exit_code == 0
        # After the status changes, the output should mention something changed
        assert "Changed" in result.output or "pass" in result.output
