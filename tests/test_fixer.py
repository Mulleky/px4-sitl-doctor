"""Tests for px4_doctor.fixer — fix collection and command extraction."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from px4_doctor.fixer import (
    _extract_commands,
    collect_fixes,
    render_fixes_dry_run,
    run_fixes,
)
from px4_doctor.models.result import CheckResult
from px4_doctor.runner import RunReport


def _make_report(results: list[CheckResult]) -> RunReport:
    return RunReport(results=results, platform="ubuntu_22_04")


# ---------------------------------------------------------------------------
# _extract_commands
# ---------------------------------------------------------------------------

class TestExtractCommands:
    def test_apt_install_extracted(self):
        cmds = _extract_commands("Install it:\n  sudo apt install ros-humble-desktop")
        assert any("sudo apt install" in c for c in cmds)

    def test_source_line_extracted(self):
        cmds = _extract_commands("Run:\n  source /opt/ros/humble/setup.bash")
        assert any("source /opt/ros" in c for c in cmds)

    def test_export_line_extracted(self):
        cmds = _extract_commands("Set the var:\n  export ROS_DOMAIN_ID=0")
        assert any("export ROS_DOMAIN_ID" in c for c in cmds)

    def test_prose_only_returns_empty(self):
        cmds = _extract_commands("This is just a description with no commands.")
        assert cmds == []

    def test_comment_lines_excluded(self):
        cmds = _extract_commands("# This is a comment\nsudo apt install foo")
        assert all(not c.startswith("#") for c in cmds)

    def test_multiple_commands_extracted(self):
        fix = (
            "First install:\n"
            "  sudo apt install colcon-common-extensions\n"
            "Then source:\n"
            "  source /opt/ros/humble/setup.bash\n"
        )
        cmds = _extract_commands(fix)
        assert len(cmds) == 2

    def test_pip_install_extracted(self):
        cmds = _extract_commands("pip install px4-sitl-doctor")
        assert any("pip install" in c for c in cmds)

    def test_snap_install_extracted(self):
        cmds = _extract_commands("  sudo snap install micro-xrce-dds-agent")
        assert any("snap install" in c for c in cmds)

    def test_git_clone_extracted(self):
        cmds = _extract_commands("  git clone https://github.com/eProsima/Micro-XRCE-DDS-Agent")
        assert any("git clone" in c for c in cmds)

    def test_empty_fix_returns_empty(self):
        assert _extract_commands("") == []


# ---------------------------------------------------------------------------
# collect_fixes
# ---------------------------------------------------------------------------

class TestCollectFixes:
    def test_collects_fail_with_fix(self):
        report = _make_report([
            CheckResult("ROS 2 Binary", "fail", "not found",
                        fix="sudo apt install ros-humble-desktop")
        ])
        fixes = collect_fixes(report)
        assert len(fixes) == 1
        result, cmds = fixes[0]
        assert result.status == "fail"
        assert any("apt install" in c for c in cmds)

    def test_collects_warn_with_fix(self):
        report = _make_report([
            CheckResult("ROS_DISTRO env var", "warn", "not set",
                        fix="source /opt/ros/humble/setup.bash")
        ])
        fixes = collect_fixes(report)
        assert len(fixes) == 1

    def test_skips_pass_results(self):
        report = _make_report([
            CheckResult("OS", "pass", "Ubuntu 22.04", fix="sudo apt update")
        ])
        fixes = collect_fixes(report)
        assert fixes == []

    def test_skips_skip_results(self):
        report = _make_report([
            CheckResult("MicroXRCE", "skip", "not applicable", fix="sudo apt install x")
        ])
        fixes = collect_fixes(report)
        assert fixes == []

    def test_skips_results_without_fix(self):
        report = _make_report([
            CheckResult("OS", "fail", "unsupported OS", fix=None)
        ])
        fixes = collect_fixes(report)
        assert fixes == []

    def test_skips_results_with_prose_only_fix(self):
        report = _make_report([
            CheckResult("OS", "fail", "bad", fix="Please refer to the documentation.")
        ])
        fixes = collect_fixes(report)
        assert fixes == []

    def test_multiple_results_collected(self):
        report = _make_report([
            CheckResult("Warn item", "warn", "minor", fix="export X=1"),
            CheckResult("Fail item", "fail", "critical", fix="sudo apt install y"),
        ])
        fixes = collect_fixes(report)
        assert len(fixes) == 2
        statuses = {r.status for r, _ in fixes}
        assert "fail" in statuses
        assert "warn" in statuses

    def test_empty_report_returns_empty(self):
        report = _make_report([])
        assert collect_fixes(report) == []


# ---------------------------------------------------------------------------
# render_fixes_dry_run (smoke tests via click.testing)
# ---------------------------------------------------------------------------

class TestRenderFixesDryRun:
    def test_no_fixes_prints_clean_message(self, capsys):
        render_fixes_dry_run([])
        out = capsys.readouterr().out
        assert "clean" in out.lower() or "no" in out.lower()

    def test_prints_command_for_each_fix(self, capsys):
        result = CheckResult("ROS 2 Binary", "fail", "missing",
                             fix="sudo apt install ros-humble-desktop")
        fixes = [(result, ["sudo apt install ros-humble-desktop"])]
        render_fixes_dry_run(fixes)
        out = capsys.readouterr().out
        assert "sudo apt install ros-humble-desktop" in out

    def test_dry_run_hint_shown(self, capsys):
        result = CheckResult("X", "fail", "bad", fix="sudo apt install foo")
        render_fixes_dry_run([(result, ["sudo apt install foo"])])
        out = capsys.readouterr().out
        assert "--run" in out


# ---------------------------------------------------------------------------
# run_fixes
# ---------------------------------------------------------------------------

class TestRunFixes:
    def test_empty_fixes_returns_zero(self, capsys):
        failed = run_fixes([])
        assert failed == 0

    def test_successful_command_returns_zero_failed(self):
        result = CheckResult("X", "fail", "bad", fix="echo ok")
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            failed = run_fixes([(result, ["echo ok"])], yes=True)
        assert failed == 0

    def test_failing_command_counted(self):
        result = CheckResult("X", "fail", "bad", fix="false")
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1)
            failed = run_fixes([(result, ["false"])], yes=True)
        assert failed == 1

    def test_exception_in_subprocess_counted_as_failure(self):
        result = CheckResult("X", "fail", "bad", fix="sudo apt install y")
        with patch("subprocess.run", side_effect=OSError("no such file")):
            failed = run_fixes([(result, ["sudo apt install y"])], yes=True)
        assert failed == 1
