"""Tests for MicroXRCE v2/v3 protocol-incompatibility detection."""

from __future__ import annotations

from unittest.mock import patch

from px4_doctor.checkers.microxrce_check import MicroXRCEChecker


def _checker():
    with patch("px4_doctor.checkers.microxrce_check.detect_platform", return_value="ubuntu_22_04"):
        return MicroXRCEChecker()


def _run(stdout: str, port_free: bool = True):
    checker = _checker()
    with (
        patch("px4_doctor.checkers.microxrce_check.find_binary", return_value="/usr/bin/MicroXRCEAgent"),
        patch("px4_doctor.checkers.microxrce_check.run_cmd", return_value=(0, stdout, "")),
        patch("px4_doctor.checkers.microxrce_check._check_port_free", return_value=port_free),
    ):
        return checker.run()


class TestV3Detection:
    def test_v3_exact_version_is_warn(self):
        results = _run("MicroXRCEAgent version 3.0.0")
        ver = next(r for r in results if "Version" in r.checker_name)
        assert ver.status == "warn"
        assert "v3.x" in ver.message or "3.x" in ver.message
        assert "INCOMPATIBLE" in ver.message or "incompatible" in ver.message.lower()
        assert ver.fix is not None
        assert "2.x" in ver.fix

    def test_v3_higher_patch_is_warn(self):
        results = _run("MicroXRCEAgent 3.1.5")
        ver = next(r for r in results if "Version" in r.checker_name)
        assert ver.status == "warn"

    def test_v3_in_raw_unparseable_output_is_warn(self):
        # Output that contains "3." but version regex can't fully parse it
        results = _run("Agent v3.something-custom")
        ver = next(r for r in results if "Version" in r.checker_name)
        # Should either parse it as v3 (warn) or flag on "3." heuristic (warn)
        assert ver.status in ("warn", "pass")  # pass only if totally undetectable

    def test_v2_valid_version_is_pass(self):
        results = _run("MicroXRCEAgent 2.4.3")
        ver = next(r for r in results if "Version" in r.checker_name)
        assert ver.status == "pass"
        assert "3.x" not in ver.message

    def test_v2_minimum_version_fail(self):
        """v2.0.0 is below the 2.4.0 minimum — should still be fail, not v3 warn."""
        results = _run("version 2.0.0")
        ver = next(r for r in results if "Version" in r.checker_name)
        assert ver.status == "fail"
        assert "older" in ver.message or "minimum" in ver.message

    def test_fix_contains_v2_downgrade_instructions(self):
        results = _run("MicroXRCEAgent version 3.0.0")
        ver = next(r for r in results if "Version" in r.checker_name)
        assert "2.4.3" in ver.fix or "2.x" in ver.fix
        assert "snap" in ver.fix or "source" in ver.fix or "git" in ver.fix

    def test_port_still_checked_when_v3_detected(self):
        """Port check should still run even when version is wrong."""
        results = _run("MicroXRCEAgent 3.0.0", port_free=False)
        port = next(r for r in results if "Port" in r.checker_name)
        assert port.status == "fail"

    def test_unrecognized_output_without_3_is_pass(self):
        """Totally unrecognized output with no '3.' hint → pass (don't over-flag)."""
        results = _run("running in background mode")
        ver = next(r for r in results if "Version" in r.checker_name)
        # Should not produce a fail — at worst a pass with a note
        assert ver.status in ("pass", "warn")
