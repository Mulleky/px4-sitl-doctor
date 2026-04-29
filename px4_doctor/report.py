"""Terminal renderer for RunReport — Rich-based with plain/JSON/Markdown fallbacks."""

from __future__ import annotations

import dataclasses
import json
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from px4_doctor.runner import RunReport

from px4_doctor import __version__
from px4_doctor.models.result import CheckResult

# Icons for each status
_ICONS = {
    "pass": "[green]✅[/green]",
    "warn": "[yellow]⚠️ [/yellow]",
    "fail": "[red]❌[/red]",
    "skip": "[dim]⏭ [/dim]",
}
_PLAIN_ICONS = {
    "pass": "PASS",
    "warn": "WARN",
    "fail": "FAIL",
    "skip": "SKIP",
}

_CATEGORY_ORDER = ["core", "env", "workspace", "network"]


def _group_by_category(results: list[CheckResult]) -> dict[str, list[CheckResult]]:
    groups: dict[str, list[CheckResult]] = {}
    for r in results:
        cat = getattr(r, "category", "core")  # CheckResult doesn't carry category by default
        groups.setdefault(cat, []).append(r)
    return groups


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def save_report_to_file(
    report: "RunReport",
    path: str,
    *,
    verbose: bool = False,
) -> None:
    """Write the report to *path*, inferring format from the file extension.

    .json → JSON, .md → Markdown, anything else → plain text.
    """
    import contextlib
    import io
    from pathlib import Path

    dest = Path(path)
    suffix = dest.suffix.lower()

    if suffix == ".json":
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            _render_json(report)
    elif suffix == ".md":
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            _render_markdown(report, verbose=verbose)
    else:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            _render_plain(report, verbose=verbose)

    dest.write_text(buf.getvalue(), encoding="utf-8")


def render_export_env(report: "RunReport") -> None:
    """Print executable export/source lines extracted from failing env check fixes."""
    import re

    # Matches export/source either at line-start or after prose like "Recommended: "
    _SHELL_RE = re.compile(
        r"(?:^|[:\s])\s*(export\s+\w\S*|source\s+\S[^\n]*?)(?:\s*#[^\n]*)?\s*$",
        re.MULTILINE,
    )

    lines: list[str] = []
    seen: set[str] = set()
    for r in report.results:
        if r.status in ("fail", "warn") and r.fix:
            for m in _SHELL_RE.finditer(r.fix):
                line = m.group(1).strip()
                if line not in seen:
                    seen.add(line)
                    lines.append(line)

    if not lines:
        print("# No missing environment configuration detected.")
        return

    print("# Add these lines to ~/.bashrc (or run them in your current shell):")
    print()
    for line in lines:
        print(line)


def render(report: "RunReport", *, verbose: bool = False,
           as_json: bool = False, as_md: bool = False, plain: bool = False) -> int:
    """Render the report to stdout. Returns the exit code."""
    if as_json:
        _render_json(report)
        return report.exit_code

    if as_md:
        _render_markdown(report, verbose=verbose)
        return report.exit_code

    if plain:
        _render_plain(report, verbose=verbose)
        return report.exit_code

    # Default: Rich
    try:
        _render_rich(report, verbose=verbose)
    except ImportError:
        _render_plain(report, verbose=verbose)

    return report.exit_code


# ---------------------------------------------------------------------------
# JSON mode
# ---------------------------------------------------------------------------

def _render_json(report: "RunReport") -> None:
    output = {
        "version": __version__,
        "platform": report.platform,
        "summary": {
            "pass": report.pass_count,
            "warn": report.warn_count,
            "fail": report.fail_count,
            "skip": report.skip_count,
            "exit_code": report.exit_code,
        },
        "results": [dataclasses.asdict(r) for r in report.results],
    }
    print(json.dumps(output, indent=2))


# ---------------------------------------------------------------------------
# Markdown mode
# ---------------------------------------------------------------------------

def _render_markdown(report: "RunReport", verbose: bool = False) -> None:
    lines = [
        f"# px4-sitl-doctor v{__version__} Report",
        f"",
        f"**Platform:** {report.platform}",
        f"",
        f"| Status | Check | Message | Fix |",
        f"|--------|-------|---------|-----|",
    ]
    for r in report.results:
        icon = {"pass": "✅", "warn": "⚠️", "fail": "❌", "skip": "⏭"}.get(r.status, "?")
        fix = r.fix.replace("\n", " ") if r.fix else ""
        msg = r.message.replace("\n", " ")
        lines.append(f"| {icon} | {r.checker_name} | {msg} | {fix} |")

    lines += [
        "",
        f"**Summary:** {report.pass_count} passed  "
        f"{report.warn_count} warnings  {report.fail_count} failures",
    ]
    print("\n".join(lines))


# ---------------------------------------------------------------------------
# Plain text (no ANSI) mode
# ---------------------------------------------------------------------------

def _render_plain(report: "RunReport", verbose: bool = False) -> None:
    width = 70
    print("=" * width)
    print(f"  px4-sitl-doctor  v{__version__}")
    print(f"  Platform: {report.platform}")
    print("=" * width)
    print()

    for r in report.results:
        icon = _PLAIN_ICONS.get(r.status, "????")
        print(f"  [{icon}]  {r.checker_name:<30}  {r.message}")
        if r.fix:
            for line in r.fix.splitlines():
                print(f"           FIX: {line}")
        if verbose and r.detail:
            for line in r.detail.splitlines():
                print(f"           DETAIL: {line}")

    print()
    print("=" * width)
    _print_summary_plain(report)
    print("=" * width)


def _print_summary_plain(report: "RunReport") -> None:
    print(
        f"  SUMMARY: {report.pass_count} passed  "
        f"{report.warn_count} warnings  {report.fail_count} failures  "
        f"{report.skip_count} skipped"
    )
    if report.has_failures:
        print("  Your environment has FAILURES that will prevent SITL launch.")
        print("  Fix the items marked [FAIL] before running PX4 SITL.")
    elif report.has_warnings:
        print("  Environment has warnings — SITL may work but review warnings above.")
    else:
        print("  All checks passed — environment looks ready for PX4 SITL!")


# ---------------------------------------------------------------------------
# Rich mode
# ---------------------------------------------------------------------------

def _render_rich(report: "RunReport", verbose: bool = False) -> None:
    from rich.console import Console  # type: ignore[import-untyped]
    from rich.panel import Panel      # type: ignore[import-untyped]
    from rich.table import Table      # type: ignore[import-untyped]
    from rich.text import Text        # type: ignore[import-untyped]
    from rich import box              # type: ignore[import-untyped]

    console = Console()

    # Header panel
    console.print(Panel.fit(
        f"[bold cyan]px4-sitl-doctor[/bold cyan]  [dim]v{__version__}[/dim]\n"
        f"[dim]Platform:[/dim] {report.platform}",
        border_style="cyan",
    ))
    console.print()

    # Group results by category (approximate — checker_name-based heuristic)
    categories = _infer_categories(report.results)

    for cat_label, cat_results in categories.items():
        console.rule(f"[bold]{cat_label}[/bold]", style="dim")
        for r in cat_results:
            icon_markup = _ICONS.get(r.status, "?")
            name_col = f"[bold]{r.checker_name}[/bold]"
            msg_color = {
                "pass": "green", "warn": "yellow", "fail": "red", "skip": "dim"
            }.get(r.status, "white")
            console.print(f"  {icon_markup}  {name_col}  [{msg_color}]{r.message}[/{msg_color}]")
            if r.fix:
                for line in r.fix.splitlines():
                    console.print(f"      [cyan]FIX:[/cyan] {line}")
            if verbose and r.detail:
                for line in r.detail.splitlines():
                    console.print(f"      [dim]DETAIL:[/dim] {line}")
        console.print()

    # Summary
    console.rule(style="dim")
    summary_color = "red" if report.has_failures else ("yellow" if report.has_warnings else "green")
    console.print(
        f"  [bold {summary_color}]SUMMARY:[/bold {summary_color}]  "
        f"[green]{report.pass_count} passed[/green]  "
        f"[yellow]{report.warn_count} warnings[/yellow]  "
        f"[red]{report.fail_count} failures[/red]  "
        f"[dim]{report.skip_count} skipped[/dim]"
    )
    if report.has_failures:
        console.print("  [red bold]Your environment has issues that will prevent SITL launch.[/red bold]")
        console.print("  [red]Fix the items marked ❌ above before running PX4 SITL.[/red]")
    elif report.has_warnings:
        console.print("  [yellow]Environment has warnings — review them before launching SITL.[/yellow]")
    else:
        console.print("  [green bold]All checks passed — environment looks ready for PX4 SITL! 🚀[/green bold]")


def _infer_categories(results: list[CheckResult]) -> dict[str, list[CheckResult]]:
    """Group results into display sections based on checker_name heuristics."""
    _MAP = {
        "OS": "OS & Python",
        "Python": "OS & Python",
        "Virtual": "OS & Python",
        "pip": "OS & Python",
        "ROS 2": "ROS 2",
        "ROS_DISTRO": "ROS 2",
        "AMENT": "ROS 2",
        "Gazebo": "Gazebo",
        "GZ_SIM": "Gazebo",
        "ROS2 +": "Gazebo",
        "PX4": "PX4",
        "MicroXRCE": "MicroXRCE-DDS",
        "XRCE": "MicroXRCE-DDS",
        "GZ_SIM_RESOURCE": "Environment Variables",
        "GZ_SIM_SYSTEM": "Environment Variables",
        "ROS_DOMAIN": "Environment Variables",
        "Port ": "Ports",
        "Network": "Network",
        "ROS 2 Workspace": "Workspace",
        "Workspace": "Workspace",
        "Package:": "Workspace",
        "WSL": "WSL2",
        "systemd": "WSL2",
        "DISPLAY": "WSL2",
    }

    groups: dict[str, list[CheckResult]] = {}
    for r in results:
        label = "Other"
        for prefix, cat in _MAP.items():
            if r.checker_name.startswith(prefix):
                label = cat
                break
        groups.setdefault(label, []).append(r)
    return groups
