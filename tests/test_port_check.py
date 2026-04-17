"""Tests for PortChecker."""

from __future__ import annotations

from unittest.mock import patch

from px4_doctor.checkers.port_check import PortChecker
from px4_doctor.models.compat_matrix import CompatMatrix


def _make_checker():
    matrix = CompatMatrix(offline=True)
    return PortChecker(matrix=matrix)


def test_pass_when_ports_free():
    checker = _make_checker()
    with patch("px4_doctor.checkers.port_check._check_port", return_value=True):
        results = checker.run()
    assert all(r.status == "pass" for r in results)


def test_fail_when_port_occupied():
    checker = _make_checker()
    # Make only the first port occupied
    ports = CompatMatrix(offline=True).get_required_ports()
    first_port = ports[0]["port"]

    def fake_check(port, protocol):
        return port != first_port

    with (
        patch("px4_doctor.checkers.port_check._check_port", side_effect=fake_check),
        patch("px4_doctor.checkers.port_check._get_port_owner", return_value=None),
    ):
        results = checker.run()

    fail_results = [r for r in results if r.status == "fail"]
    assert fail_results, "Expected at least one failure for occupied port"
    assert fail_results[0].fix is not None


def test_skips_when_no_matrix():
    checker = PortChecker(matrix=None)
    results = checker.run()
    assert results[0].status == "skip"
