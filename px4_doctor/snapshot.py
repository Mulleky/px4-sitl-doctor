"""Environment snapshot — save and diff px4-doctor run reports."""

from __future__ import annotations

import dataclasses
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

import click

from px4_doctor import __version__

if TYPE_CHECKING:
    from px4_doctor.runner import RunReport


def save_snapshot(report: "RunReport", path: str) -> None:
    """Serialize report to a JSON snapshot file with a UTC timestamp."""
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)

    data = {
        "px4_doctor_version": __version__,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "platform": report.platform,
        "summary": {
            "pass": report.pass_count,
            "warn": report.warn_count,
            "fail": report.fail_count,
            "skip": report.skip_count,
        },
        "results": [dataclasses.asdict(r) for r in report.results],
    }
    dest.write_text(json.dumps(data, indent=2), encoding="utf-8")


def load_snapshot(path: str) -> dict:
    """Load and validate a snapshot file. Raises click.ClickException on error."""
    src = Path(path)
    if not src.exists():
        raise click.ClickException(f"Snapshot file not found: {path}")
    try:
        data = json.loads(src.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise click.ClickException(f"Could not read snapshot: {exc}") from exc
    if "results" not in data:
        raise click.ClickException(f"File does not look like a px4-doctor snapshot: {path}")
    return data


def diff_snapshots(saved: dict, current: "RunReport") -> list[dict]:
    """Return a list of changed checks: {checker_name, before, after}."""
    saved_map: dict[str, str] = {r["checker_name"]: r["status"] for r in saved["results"]}
    current_map: dict[str, str] = {r.checker_name: r.status for r in current.results}

    all_names = sorted(set(saved_map) | set(current_map))
    changes = []
    for name in all_names:
        before = saved_map.get(name, "missing")
        after = current_map.get(name, "missing")
        if before != after:
            changes.append({"checker_name": name, "before": before, "after": after})
    return changes


def render_diff(saved: dict, current: "RunReport", *, plain: bool = False) -> None:
    """Print a human-readable diff between a snapshot and the current run."""
    changes = diff_snapshots(saved, current)
    timestamp = saved.get("timestamp", "unknown")
    saved_platform = saved.get("platform", "unknown")

    try:
        dt = datetime.fromisoformat(timestamp)
        now = datetime.now(timezone.utc)
        age_hours = (now - dt).total_seconds() / 3600
        if age_hours < 1:
            age_str = f"{int(age_hours * 60)} minutes ago"
        elif age_hours < 48:
            age_str = f"{age_hours:.1f} hours ago"
        else:
            age_str = f"{age_hours / 24:.1f} days ago"
        time_str = f"{timestamp}  ({age_str})"
    except (ValueError, TypeError):
        time_str = timestamp

    if plain:
        _render_diff_plain(changes, time_str, saved_platform, current)
    else:
        try:
            _render_diff_rich(changes, time_str, saved_platform, current)
        except ImportError:
            _render_diff_plain(changes, time_str, saved_platform, current)


def _render_diff_plain(
    changes: list[dict],
    time_str: str,
    saved_platform: str,
    current: "RunReport",
) -> None:
    print(f"Snapshot taken : {time_str}")
    print(f"Snapshot platform: {saved_platform}")
    print(f"Current platform : {current.platform}")
    print()

    if not changes:
        print("No changes since snapshot — environment is identical.")
        return

    print(f"Changes ({len(changes)}):")
    for ch in changes:
        arrow = f"{ch['before']} -> {ch['after']}"
        fixed = " (fixed!)" if ch["before"] == "fail" and ch["after"] == "pass" else ""
        broken = " (BROKEN!)" if ch["before"] == "pass" and ch["after"] == "fail" else ""
        print(f"  {ch['checker_name']:<35} {arrow}{fixed}{broken}")

    regressions = [c for c in changes if c["before"] == "pass" and c["after"] == "fail"]
    resolved = [c for c in changes if c["before"] == "fail" and c["after"] == "pass"]
    print()
    if regressions:
        print(f"REGRESSIONS: {len(regressions)} check(s) that were passing are now failing.")
    if resolved:
        print(f"Resolved   : {len(resolved)} check(s) fixed since snapshot.")


def _render_diff_rich(
    changes: list[dict],
    time_str: str,
    saved_platform: str,
    current: "RunReport",
) -> None:
    from rich.console import Console  # type: ignore[import-untyped]
    from rich.panel import Panel      # type: ignore[import-untyped]
    from rich.table import Table      # type: ignore[import-untyped]
    from rich import box              # type: ignore[import-untyped]

    console = Console()
    console.print(Panel.fit(
        "[bold cyan]px4-sitl-doctor[/bold cyan]  [dim]—  Snapshot Diff[/dim]\n"
        f"[dim]Snapshot:[/dim] {time_str}\n"
        f"[dim]Platform:[/dim] {current.platform}",
        border_style="cyan",
    ))
    console.print()

    if not changes:
        console.print("[green bold]No changes since snapshot — environment is identical.[/green bold]")
        return

    table = Table(box=box.ROUNDED, show_header=True, header_style="bold")
    table.add_column("Check", width=38)
    table.add_column("Before", width=8)
    table.add_column("After", width=8)
    table.add_column("Note", width=12)

    _COLORS = {"pass": "green", "fail": "red", "warn": "yellow", "skip": "dim", "missing": "dim"}
    _ICONS = {"pass": "✅", "fail": "❌", "warn": "⚠️ ", "skip": "⏭ ", "missing": "—"}

    regressions = 0
    resolved = 0

    for ch in changes:
        before_color = _COLORS.get(ch["before"], "white")
        after_color = _COLORS.get(ch["after"], "white")
        before_icon = _ICONS.get(ch["before"], "?")
        after_icon = _ICONS.get(ch["after"], "?")

        if ch["before"] == "fail" and ch["after"] == "pass":
            note = "[green]fixed ✓[/green]"
            resolved += 1
        elif ch["before"] == "pass" and ch["after"] == "fail":
            note = "[red bold]BROKEN[/red bold]"
            regressions += 1
        elif ch["after"] == "missing":
            note = "[dim]removed[/dim]"
        elif ch["before"] == "missing":
            note = "[dim]new[/dim]"
        else:
            note = ""

        table.add_row(
            ch["checker_name"],
            f"[{before_color}]{before_icon}[/{before_color}]",
            f"[{after_color}]{after_icon}[/{after_color}]",
            note,
        )

    console.print(table)
    console.print()

    if regressions:
        console.print(
            f"[red bold]  {regressions} regression(s) — checks that were passing are now failing.[/red bold]"
        )
    if resolved:
        console.print(f"[green]  {resolved} issue(s) resolved since snapshot.[/green]")
    if not regressions and not resolved:
        console.print("[dim]  Changes in warn/skip status only — no regressions or fixes.[/dim]")
