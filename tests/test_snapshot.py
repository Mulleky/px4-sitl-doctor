"""Tests for px4_doctor.snapshot — save, load, diff."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from px4_doctor.models.result import CheckResult
from px4_doctor.runner import RunReport
from px4_doctor.snapshot import (
    diff_snapshots,
    load_snapshot,
    render_diff,
    save_snapshot,
)


def _report(*results: CheckResult) -> RunReport:
    return RunReport(results=list(results), platform="ubuntu_22_04")


# ---------------------------------------------------------------------------
# save_snapshot
# ---------------------------------------------------------------------------

class TestSaveSnapshot:
    def test_creates_file(self, tmp_path):
        dest = str(tmp_path / "snap.json")
        save_snapshot(_report(), dest)
        assert Path(dest).exists()

    def test_output_is_valid_json(self, tmp_path):
        dest = str(tmp_path / "snap.json")
        save_snapshot(_report(CheckResult("OS", "pass", "ok")), dest)
        data = json.loads(Path(dest).read_text(encoding="utf-8"))
        assert isinstance(data, dict)

    def test_contains_required_keys(self, tmp_path):
        dest = str(tmp_path / "snap.json")
        save_snapshot(_report(), dest)
        data = json.loads(Path(dest).read_text(encoding="utf-8"))
        for key in ("px4_doctor_version", "timestamp", "platform", "summary", "results"):
            assert key in data, f"Missing key: {key}"

    def test_results_serialized(self, tmp_path):
        dest = str(tmp_path / "snap.json")
        report = _report(
            CheckResult("OS Version", "pass", "Ubuntu 22.04"),
            CheckResult("ROS 2 Binary", "fail", "not found"),
        )
        save_snapshot(report, dest)
        data = json.loads(Path(dest).read_text(encoding="utf-8"))
        names = {r["checker_name"] for r in data["results"]}
        assert "OS Version" in names
        assert "ROS 2 Binary" in names

    def test_summary_counts_correct(self, tmp_path):
        dest = str(tmp_path / "snap.json")
        report = _report(
            CheckResult("A", "pass", "ok"),
            CheckResult("B", "fail", "bad"),
            CheckResult("C", "warn", "maybe"),
        )
        save_snapshot(report, dest)
        data = json.loads(Path(dest).read_text(encoding="utf-8"))
        assert data["summary"]["pass"] == 1
        assert data["summary"]["fail"] == 1
        assert data["summary"]["warn"] == 1

    def test_creates_parent_dirs(self, tmp_path):
        dest = str(tmp_path / "nested" / "dir" / "snap.json")
        save_snapshot(_report(), dest)
        assert Path(dest).exists()

    def test_timestamp_is_iso_format(self, tmp_path):
        from datetime import datetime
        dest = str(tmp_path / "snap.json")
        save_snapshot(_report(), dest)
        data = json.loads(Path(dest).read_text(encoding="utf-8"))
        # Should not raise
        datetime.fromisoformat(data["timestamp"])


# ---------------------------------------------------------------------------
# load_snapshot
# ---------------------------------------------------------------------------

class TestLoadSnapshot:
    def test_loads_valid_file(self, tmp_path):
        dest = str(tmp_path / "snap.json")
        save_snapshot(_report(CheckResult("OS", "pass", "ok")), dest)
        data = load_snapshot(dest)
        assert "results" in data

    def test_missing_file_raises_click_exception(self, tmp_path):
        import click
        with pytest.raises(click.ClickException):
            load_snapshot(str(tmp_path / "nonexistent.json"))

    def test_invalid_json_raises_click_exception(self, tmp_path):
        import click
        bad = tmp_path / "bad.json"
        bad.write_text("not json at all {{{", encoding="utf-8")
        with pytest.raises(click.ClickException):
            load_snapshot(str(bad))

    def test_json_without_results_key_raises_click_exception(self, tmp_path):
        import click
        bad = tmp_path / "bad.json"
        bad.write_text(json.dumps({"foo": "bar"}), encoding="utf-8")
        with pytest.raises(click.ClickException):
            load_snapshot(str(bad))


# ---------------------------------------------------------------------------
# diff_snapshots
# ---------------------------------------------------------------------------

class TestDiffSnapshots:
    def _saved(self, *results: CheckResult) -> dict:
        import dataclasses
        return {
            "platform": "ubuntu_22_04",
            "results": [dataclasses.asdict(r) for r in results],
        }

    def test_no_change_returns_empty(self):
        saved = self._saved(CheckResult("OS", "pass", "ok"))
        current = _report(CheckResult("OS", "pass", "ok"))
        changes = diff_snapshots(saved, current)
        assert changes == []

    def test_status_change_detected(self):
        saved = self._saved(CheckResult("ROS 2 Binary", "fail", "missing"))
        current = _report(CheckResult("ROS 2 Binary", "pass", "found"))
        changes = diff_snapshots(saved, current)
        assert len(changes) == 1
        assert changes[0]["checker_name"] == "ROS 2 Binary"
        assert changes[0]["before"] == "fail"
        assert changes[0]["after"] == "pass"

    def test_new_check_appears_as_missing_before(self):
        saved = self._saved()
        current = _report(CheckResult("New Check", "pass", "ok"))
        changes = diff_snapshots(saved, current)
        assert any(c["checker_name"] == "New Check" and c["before"] == "missing" for c in changes)

    def test_removed_check_appears_as_missing_after(self):
        saved = self._saved(CheckResult("Old Check", "pass", "ok"))
        current = _report()
        changes = diff_snapshots(saved, current)
        assert any(c["checker_name"] == "Old Check" and c["after"] == "missing" for c in changes)

    def test_multiple_changes_all_reported(self):
        saved = self._saved(
            CheckResult("A", "fail", "bad"),
            CheckResult("B", "pass", "ok"),
            CheckResult("C", "warn", "maybe"),
        )
        current = _report(
            CheckResult("A", "pass", "fixed"),
            CheckResult("B", "fail", "broken"),
            CheckResult("C", "warn", "maybe"),  # unchanged
        )
        changes = diff_snapshots(saved, current)
        names = {c["checker_name"] for c in changes}
        assert "A" in names
        assert "B" in names
        assert "C" not in names  # unchanged


# ---------------------------------------------------------------------------
# render_diff (smoke tests)
# ---------------------------------------------------------------------------

class TestRenderDiff:
    def _make_saved(self, *results: CheckResult) -> dict:
        import dataclasses
        return {
            "platform": "ubuntu_22_04",
            "timestamp": "2026-04-29T10:00:00+00:00",
            "results": [dataclasses.asdict(r) for r in results],
        }

    def test_no_changes_plain(self, capsys):
        saved = self._make_saved(CheckResult("OS", "pass", "ok"))
        current = _report(CheckResult("OS", "pass", "ok"))
        render_diff(saved, current, plain=True)
        out = capsys.readouterr().out
        assert "No changes" in out or "identical" in out

    def test_regression_highlighted_plain(self, capsys):
        saved = self._make_saved(CheckResult("ROS 2 Binary", "pass", "was ok"))
        current = _report(CheckResult("ROS 2 Binary", "fail", "now broken"))
        render_diff(saved, current, plain=True)
        out = capsys.readouterr().out
        assert "BROKEN" in out or "regression" in out.lower()

    def test_resolved_issue_highlighted_plain(self, capsys):
        saved = self._make_saved(CheckResult("ROS 2 Binary", "fail", "was broken"))
        current = _report(CheckResult("ROS 2 Binary", "pass", "now fixed"))
        render_diff(saved, current, plain=True)
        out = capsys.readouterr().out
        assert "fixed" in out.lower() or "resolved" in out.lower()

    def test_timestamp_shown(self, capsys):
        saved = self._make_saved(CheckResult("OS", "pass", "ok"))
        current = _report(CheckResult("OS", "pass", "ok"))
        render_diff(saved, current, plain=True)
        out = capsys.readouterr().out
        assert "2026-04-29" in out

    def test_rich_render_does_not_crash(self, capsys):
        saved = self._make_saved(CheckResult("OS", "pass", "ok"))
        current = _report(CheckResult("OS", "fail", "broken"))
        try:
            render_diff(saved, current, plain=False)
        except ImportError:
            pytest.skip("Rich not installed")
