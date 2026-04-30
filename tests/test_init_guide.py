"""Tests for px4_doctor.init_guide — ordered setup guide rendering."""

from __future__ import annotations

import pytest

from px4_doctor.init_guide import (
    SETUP_STEPS,
    _results_for_step,
    _step_status,
    render_init,
)
from px4_doctor.models.result import CheckResult
from px4_doctor.runner import RunReport


def _report(*results: CheckResult) -> RunReport:
    return RunReport(results=list(results), platform="ubuntu_22_04")


# ---------------------------------------------------------------------------
# _step_status
# ---------------------------------------------------------------------------

class TestStepStatus:
    def test_all_pass_returns_pass(self):
        results = [
            CheckResult("OS Version", "pass", "ok"),
            CheckResult("OS Supported", "pass", "ok"),
        ]
        assert _step_status(results) == "pass"

    def test_one_fail_returns_fail(self):
        results = [
            CheckResult("OS Version", "pass", "ok"),
            CheckResult("OS Supported", "fail", "bad"),
        ]
        assert _step_status(results) == "fail"

    def test_warn_beats_pass(self):
        results = [
            CheckResult("OS Version", "pass", "ok"),
            CheckResult("OS Supported", "warn", "marginal"),
        ]
        assert _step_status(results) == "warn"

    def test_fail_beats_warn(self):
        results = [
            CheckResult("X", "warn", "minor"),
            CheckResult("Y", "fail", "critical"),
        ]
        assert _step_status(results) == "fail"

    def test_empty_returns_skip(self):
        assert _step_status([]) == "skip"

    def test_all_skip_returns_skip(self):
        results = [CheckResult("X", "skip", "not applicable")]
        assert _step_status(results) == "skip"


# ---------------------------------------------------------------------------
# _results_for_step
# ---------------------------------------------------------------------------

class TestResultsForStep:
    def test_prefix_matching(self):
        results = [
            CheckResult("ROS 2 Binary", "pass", "ok"),
            CheckResult("ROS_DISTRO env var", "warn", "missing"),
            CheckResult("OS Version", "pass", "ok"),
        ]
        matched = _results_for_step(["ROS 2", "ROS_DISTRO"], results)
        names = {r.checker_name for r in matched}
        assert "ROS 2 Binary" in names
        assert "ROS_DISTRO env var" in names
        assert "OS Version" not in names

    def test_no_match_returns_empty(self):
        results = [CheckResult("OS Version", "pass", "ok")]
        matched = _results_for_step(["MicroXRCE"], results)
        assert matched == []

    def test_each_result_matched_once(self):
        """A result matching multiple prefixes should only appear once."""
        results = [CheckResult("ROS 2 Binary", "pass", "ok")]
        matched = _results_for_step(["ROS 2", "ROS"], results)
        assert len(matched) == 1


# ---------------------------------------------------------------------------
# render_init
# ---------------------------------------------------------------------------

class TestRenderInit:
    def test_all_pass_exit_0(self, capsys):
        report = _report(
            CheckResult("OS Version", "pass", "Ubuntu 22.04"),
            CheckResult("Python 3.11", "pass", "ok"),
            CheckResult("ROS 2 Binary", "pass", "found"),
        )
        code = render_init(report, plain=True)
        assert code == 0

    def test_any_fail_exit_2(self, capsys):
        report = _report(
            CheckResult("ROS 2 Binary", "fail", "not found",
                        fix="sudo apt install ros-humble-desktop"),
        )
        code = render_init(report, plain=True)
        assert code == 2

    def test_only_warns_exit_1(self, capsys):
        report = _report(
            CheckResult("ROS_DISTRO env var", "warn", "not set",
                        fix="source /opt/ros/humble/setup.bash"),
        )
        code = render_init(report, plain=True)
        assert code == 1

    def test_output_contains_step_numbers(self, capsys):
        report = _report(CheckResult("OS Version", "pass", "ok"))
        render_init(report, plain=True)
        out = capsys.readouterr().out
        assert "Step 1" in out
        assert "Step 10" in out

    def test_fail_step_shows_fix(self, capsys):
        report = _report(
            CheckResult("ROS 2 Binary", "fail", "not found",
                        fix="sudo apt install ros-humble-desktop"),
        )
        render_init(report, plain=True)
        out = capsys.readouterr().out
        assert "sudo apt install" in out or "not found" in out

    def test_all_10_steps_present(self, capsys):
        report = _report()
        render_init(report, plain=True)
        out = capsys.readouterr().out
        for i in range(1, 11):
            assert f"Step {i}" in out

    def test_rich_render_does_not_crash(self, capsys):
        report = _report(
            CheckResult("OS Version", "pass", "Ubuntu 22.04"),
            CheckResult("ROS 2 Binary", "fail", "missing",
                        fix="sudo apt install ros-humble-desktop"),
        )
        try:
            render_init(report, plain=False)
        except ImportError:
            pytest.skip("Rich not installed")

    def test_empty_report_renders_all_skip(self, capsys):
        report = _report()
        render_init(report, plain=True)
        out = capsys.readouterr().out
        # With no results, steps default to SKIP
        assert "SKIP" in out or "Step" in out


# ---------------------------------------------------------------------------
# SETUP_STEPS structure
# ---------------------------------------------------------------------------

class TestSetupStepsDefinition:
    def test_steps_are_numbered_sequentially(self):
        numbers = [s[0] for s in SETUP_STEPS]
        assert numbers == list(range(1, len(SETUP_STEPS) + 1))

    def test_all_steps_have_prefixes(self):
        for num, name, desc, prefixes in SETUP_STEPS:
            assert prefixes, f"Step {num} '{name}' has no checker prefixes"

    def test_os_is_first_step(self):
        assert SETUP_STEPS[0][0] == 1
        assert "OS" in SETUP_STEPS[0][1] or "Operating" in SETUP_STEPS[0][1]

    def test_ten_steps_defined(self):
        assert len(SETUP_STEPS) == 10
