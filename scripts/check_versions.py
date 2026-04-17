#!/usr/bin/env python3
"""
Monthly upstream version monitor for px4-sitl-doctor.

Queries GitHub Releases and endoflife.date to detect new major versions of
PX4, Gazebo, ROS 2, and MicroXRCEAgent, then compares against the known
combos in compatibility.yaml.

Exit codes:
  0 — no new major versions detected
  1 — one or more new major/distro versions found (review needed)
  2 — error fetching upstream data

Usage:
  python scripts/check_versions.py
  python scripts/check_versions.py --json      # machine-readable output
  python scripts/check_versions.py --quiet     # suppress output, rely on exit code
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

import yaml

# ── constants ──────────────────────────────────────────────────────────────── #

COMPAT_YAML = Path(__file__).parent.parent / "px4_doctor" / "data" / "compatibility.yaml"
TIMEOUT = 8

GITHUB_LATEST = "https://api.github.com/repos/{owner}/{repo}/releases/latest"
GITHUB_RELEASES = "https://api.github.com/repos/{owner}/{repo}/releases?per_page=20"
ENDOFLIFE_URL = "https://endoflife.date/api/{product}.json"

REPOS = {
    "px4": ("PX4", "PX4-Autopilot"),
    "microxrce": ("eProsima", "Micro-XRCE-DDS-Agent"),
    "gazebo": ("gazebosim", "gz-sim"),
}

# Gazebo release names in version order (append new ones here when released)
GAZEBO_VERSION_TO_NAME = {
    7: "garden",
    8: "harmonic",
    9: "ionic",
    10: "jetty",
}


# ── helpers ────────────────────────────────────────────────────────────────── #

def _get(url: str) -> Any:
    """Fetch JSON from *url*. Raises on network error."""
    try:
        import urllib.request
        req = urllib.request.Request(url, headers={"User-Agent": "px4-sitl-doctor/check-versions"})
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return json.loads(resp.read().decode())
    except Exception as exc:
        raise RuntimeError(f"Failed to fetch {url}: {exc}") from exc


def _parse_semver(tag: str) -> tuple[int, int, int]:
    """Convert 'v1.15.2' or '1.15.2' to (1, 15, 2). Returns (0,0,0) on parse error."""
    tag = tag.lstrip("vV").split("-")[0]
    parts = tag.split(".")
    try:
        major = int(parts[0]) if len(parts) > 0 else 0
        minor = int(parts[1]) if len(parts) > 1 else 0
        patch = int(parts[2]) if len(parts) > 2 else 0
        return (major, minor, patch)
    except (ValueError, IndexError):
        return (0, 0, 0)


def latest_github_release(owner: str, repo: str) -> tuple[str, tuple[int, int, int]]:
    """Return (tag_name, (major, minor, patch)) of the latest stable release."""
    data = _get(GITHUB_LATEST.format(owner=owner, repo=repo))
    tag = data["tag_name"]
    return tag, _parse_semver(tag)


def latest_gazebo_major() -> int:
    """Return the highest gz-sim major version found across recent releases.

    Tags use the format gz-simN_N.M.P (e.g. gz-sim8_8.7.0), not plain semver.
    """
    releases = _get(GITHUB_RELEASES.format(owner="gazebosim", repo="gz-sim"))
    majors = set()
    for rel in releases:
        if rel.get("prerelease") or rel.get("draft"):
            continue
        m = re.match(r"gz-sim(\d+)_", rel["tag_name"])
        if m:
            majors.add(int(m.group(1)))
    return max(majors) if majors else 0


def ros2_distros() -> list[dict]:
    """Return active ROS 2 distros from endoflife.date."""
    return _get(ENDOFLIFE_URL.format(product="ros-2"))


# ── core logic ─────────────────────────────────────────────────────────────── #

def load_matrix() -> dict:
    return yaml.safe_load(COMPAT_YAML.read_text(encoding="utf-8"))


def known_ros2_distros(matrix: dict) -> set[str]:
    return {c["ros2"].lower() for c in matrix.get("combos", [])}


def known_gazebo_majors(matrix: dict) -> set[int]:
    return {c["gazebo_major"] for c in matrix.get("combos", [])}


def known_px4_max(matrix: dict) -> tuple[int, int, int]:
    """Return the highest px4_max version tracked (None entries → treated as very high)."""
    best = (0, 0, 0)
    for combo in matrix.get("combos", []):
        px4_max = combo.get("px4_max")
        if px4_max is None:
            return (999, 999, 999)  # open-ended
        v = _parse_semver(str(px4_max))
        if v > best:
            best = v
    return best


def run_checks() -> tuple[list[dict], list[str]]:
    """Return (findings, errors). Findings are dicts with 'kind', 'new', 'status'."""
    matrix = load_matrix()
    findings: list[dict] = []
    errors: list[str] = []

    # ── PX4 ──────────────────────────────────────────────────────────────── #
    try:
        tag, ver = latest_github_release(*REPOS["px4"])
        known_max = known_px4_max(matrix)
        status = "ok" if ver <= known_max else "NEW_MAJOR"
        findings.append({
            "component": "PX4 Autopilot",
            "latest_tag": tag,
            "latest_version": f"{ver[0]}.{ver[1]}.{ver[2]}",
            "status": status,
            "detail": f"matrix tracks up to {known_max[0]}.{known_max[1]}.{known_max[2]}"
                      if known_max[0] < 900 else "matrix has open-ended px4_max",
        })
    except RuntimeError as e:
        errors.append(f"PX4: {e}")

    # ── Gazebo ───────────────────────────────────────────────────────────── #
    try:
        gz_major = latest_gazebo_major()
        known = known_gazebo_majors(matrix)
        status = "ok" if gz_major in known else "NEW_MAJOR"
        gz_name = GAZEBO_VERSION_TO_NAME.get(gz_major, f"v{gz_major} (unknown name)")
        findings.append({
            "component": "Gazebo",
            "latest_tag": f"gz-sim {gz_major}.x",
            "latest_version": str(gz_major),
            "gazebo_name": gz_name,
            "status": status,
            "detail": f"matrix knows majors {sorted(known)}",
        })
    except RuntimeError as e:
        errors.append(f"Gazebo: {e}")

    # ── MicroXRCEAgent ───────────────────────────────────────────────────── #
    try:
        tag, ver = latest_github_release(*REPOS["microxrce"])
        findings.append({
            "component": "MicroXRCEAgent",
            "latest_tag": tag,
            "latest_version": f"{ver[0]}.{ver[1]}.{ver[2]}",
            "status": "info",
            "detail": "no major-version gating in matrix; review if API breaking changes",
        })
    except RuntimeError as e:
        errors.append(f"MicroXRCEAgent: {e}")

    # ── ROS 2 ────────────────────────────────────────────────────────────── #
    try:
        distros = ros2_distros()
        known = known_ros2_distros(matrix)
        today = __import__("datetime").date.today().isoformat()
        for distro in distros:
            name = distro.get("cycle", "").lower()
            eol = distro.get("eol", "")
            active = eol is False or (isinstance(eol, str) and eol > today)
            if not active:
                continue
            status = "ok" if name in known else "NEW_DISTRO"
            findings.append({
                "component": f"ROS 2 ({name})",
                "latest_tag": name,
                "latest_version": name,
                "eol": eol,
                "status": status,
                "detail": "already in matrix" if name in known else "NOT in compatibility.yaml — review needed",
            })
    except RuntimeError as e:
        errors.append(f"ROS 2: {e}")

    return findings, errors


# ── output ─────────────────────────────────────────────────────────────────── #

_STATUS_LABEL = {
    "ok": "  OK ",
    "NEW_MAJOR": " NEW ",
    "NEW_DISTRO": " NEW ",
    "info": "INFO ",
}

_STATUS_PREFIX = {
    "ok": "✅",
    "NEW_MAJOR": "🆕",
    "NEW_DISTRO": "🆕",
    "info": "ℹ️ ",
}


def print_report(findings: list[dict], errors: list[str]) -> None:
    print("\n─── Upstream Version Check ────────────────────────────────────")
    for f in findings:
        icon = _STATUS_PREFIX.get(f["status"], "❓")
        label = _STATUS_LABEL.get(f["status"], " ??? ")
        print(f"  {icon} [{label}] {f['component']:<22} {f['latest_tag']:<18}  {f['detail']}")
    if errors:
        print("\n── Fetch errors ─────────────────────────────────────────────")
        for e in errors:
            print(f"  ⚠️  {e}")
    print()


def needs_review(findings: list[dict]) -> bool:
    return any(f["status"] in ("NEW_MAJOR", "NEW_DISTRO") for f in findings)


# ── entry point ────────────────────────────────────────────────────────────── #

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--json", action="store_true", help="Output JSON instead of text")
    parser.add_argument("--quiet", action="store_true", help="Suppress output; rely on exit code")
    args = parser.parse_args()

    try:
        findings, errors = run_checks()
    except Exception as exc:
        if not args.quiet:
            print(f"Error: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps({"findings": findings, "errors": errors}, indent=2))
    elif not args.quiet:
        print_report(findings, errors)

    if errors and not findings:
        return 2
    return 1 if needs_review(findings) else 0


if __name__ == "__main__":
    sys.exit(main())
