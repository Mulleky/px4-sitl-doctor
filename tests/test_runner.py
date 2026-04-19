"""Integration tests for DoctorRunner and RunReport."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from px4_doctor.models.result import CheckResult
from px4_doctor.runner import DoctorRunner, RunOptions, RunReport


def _make_result(status: str, name: str = "TestCheck") -> CheckResult:
    return CheckResult(
        checker_name=name,
        status=status,
        message=f"Test result: {status}",
        fix="fix command" if status in ("fail", "warn") else None,
    )


class TestRunReport:
    def test_exit_code_all_pass(self):
        results = [_make_result("pass"), _make_result("skip")]
        report = RunReport(results=results, platform="ubuntu_22_04")
        assert report.exit_code == 0

    def test_exit_code_warnings(self):
        results = [_make_result("pass"), _make_result("warn")]
        report = RunReport(results=results, platform="ubuntu_22_04")
        assert report.exit_code == 1

    def test_exit_code_failures(self):
        results = [_make_result("fail"), _make_result("warn")]
        report = RunReport(results=results, platform="ubuntu_22_04")
        assert report.exit_code == 2

    def test_counts(self):
        results = [
            _make_result("pass"),
            _make_result("pass"),
            _make_result("warn"),
            _make_result("fail"),
            _make_result("skip"),
        ]
        report = RunReport(results=results, platform="ubuntu_22_04")
        assert report.pass_count == 2
        assert report.warn_count == 1
        assert report.fail_count == 1
        assert report.skip_count == 1

    def test_has_failures(self):
        results = [_make_result("fail")]
        report = RunReport(results=results, platform="ubuntu_22_04")
        assert report.has_failures is True

    def test_no_failures(self):
        results = [_make_result("pass")]
        report = RunReport(results=results, platform="ubuntu_22_04")
        assert report.has_failures is False


class TestDoctorRunner:
    def test_run_all_returns_report(self):
        options = RunOptions(offline=True)
        with patch("px4_doctor.runner.detect_platform", return_value="ubuntu_22_04"):
            runner = DoctorRunner(options)
            report = runner.run_all()
        assert isinstance(report, RunReport)
        assert isinstance(report.results, list)
        assert isinstance(report.exit_code, int)

    def test_only_filter(self):
        """--only os,python should run only those two checkers."""
        options = RunOptions(offline=True, only=["os", "python"])
        with patch("px4_doctor.runner.detect_platform", return_value="ubuntu_22_04"):
            runner = DoctorRunner(options)
            # Verify _build_checkers returns <= 2 checkers
            checkers = runner._build_checkers()
        assert len(checkers) <= 2

    def test_skip_filter(self):
        """--skip network should exclude the network checker."""
        options = RunOptions(offline=True, skip=["network"])
        with patch("px4_doctor.runner.detect_platform", return_value="ubuntu_22_04"):
            runner = DoctorRunner(options)
            checkers = runner._build_checkers()
        checker_names = [type(c).__name__ for c in checkers]
        assert "NetworkChecker" not in checker_names

    def test_checker_exception_produces_fail(self):
        """If a checker raises, runner should produce a fail result."""
        from px4_doctor.checkers.base import BaseChecker

        class BrokenChecker(BaseChecker):
            name = "Broken"
            category = "core"
            platforms = ["all"]

            def run(self):
                raise RuntimeError("unexpected boom")

        options = RunOptions(offline=True, only=["os"])  # minimize real checkers
        with patch("px4_doctor.runner.detect_platform", return_value="ubuntu_22_04"):
            runner = DoctorRunner(options)
            runner._build_checkers = lambda: [BrokenChecker()]
            report = runner.run_all()

        fail_results = [r for r in report.results if r.status == "fail"]
        assert fail_results
        # Regression for issue #4: the traceback must be preserved in detail,
        # not just str(exc), so --verbose can show it.
        boom = [r for r in fail_results if r.checker_name == "Broken"]
        assert boom, "BrokenChecker should have produced a fail result"
        assert boom[0].detail is not None
        assert "RuntimeError" in boom[0].detail
        assert "unexpected boom" in boom[0].detail
        assert "Traceback" in boom[0].detail

    def test_exit_code_empty_results(self):
        """Zero results (e.g. --only with unknown name) should exit 0 cleanly."""
        report = RunReport(results=[], platform="ubuntu_22_04")
        assert report.exit_code == 0
        assert report.pass_count == 0
        assert report.fail_count == 0

    def test_checker_returning_malformed_does_not_crash(self):
        from px4_doctor.checkers.base import BaseChecker

        class WeirdChecker(BaseChecker):
            name = "Weird"
            category = "core"
            platforms = ["all"]

            def run(self):
                # Returns empty list — legal but edge case
                return []

        options = RunOptions(offline=True)
        with patch("px4_doctor.runner.detect_platform", return_value="ubuntu_22_04"):
            runner = DoctorRunner(options)
            runner._build_checkers = lambda: [WeirdChecker()]
            report = runner.run_all()
        assert report.results == []
        assert report.exit_code == 0
