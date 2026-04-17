"""Tests for LibraryChecker."""

from __future__ import annotations

from unittest.mock import patch

from px4_doctor.checkers.library_check import LibraryChecker
from px4_doctor.models.compat_matrix import CompatMatrix


def _make_checker(platform="ubuntu_22_04"):
    with patch("px4_doctor.checkers.library_check.detect_platform", return_value=platform):
        matrix = CompatMatrix(offline=True)
        return LibraryChecker(matrix=matrix)


def test_skips_on_windows_native():
    with patch("px4_doctor.checkers.library_check.detect_platform", return_value="windows_native"):
        matrix = CompatMatrix(offline=True)
        checker = LibraryChecker(matrix=matrix)
    results = checker.run()
    assert results[0].status == "skip"


def test_warn_when_library_not_found(tmp_path):
    checker = _make_checker()
    with (
        patch("px4_doctor.checkers.library_check._ldconfig_paths", return_value=set()),
        patch("pathlib.Path.exists", return_value=False),
    ):
        results = checker.run()
    warn_results = [r for r in results if r.status == "warn"]
    assert warn_results, "Expected warnings for missing libraries"
    for r in warn_results:
        assert r.fix is not None
