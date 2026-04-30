"""Ordered setup guide — maps check results onto a dependency-ordered step list."""

from __future__ import annotations

from typing import TYPE_CHECKING

import click

if TYPE_CHECKING:
    from px4_doctor.runner import RunReport
    from px4_doctor.models.result import CheckResult

# Each step: (number, display_name, description, checker_name_prefixes)
# Prefixes are matched against CheckResult.checker_name with str.startswith().
SETUP_STEPS: list[tuple[int, str, str, list[str]]] = [
    (
        1, "Operating System",
        "Ubuntu 22.04/24.04 LTS or Windows with WSL2",
        ["OS", "WSL", "Virtual", "systemd", "DISPLAY"],
    ),
    (
        2, "Python",
        "Python 3.10+ on PATH",
        ["Python", "pip"],
    ),
    (
        3, "ROS 2 installed & sourced",
        "ROS 2 Humble or Jazzy installed and setup.bash sourced",
        ["ROS 2", "ROS_DISTRO", "AMENT", "ROS 2 Sourced", "ROS 2 Compatibility"],
    ),
    (
        4, "Gazebo simulator",
        "Gazebo Harmonic or Ionic binary on PATH",
        ["Gazebo", "GZ_SIM", "ROS2 +"],
    ),
    (
        5, "PX4-Autopilot cloned & built",
        "PX4-Autopilot repository cloned and SITL target built",
        ["PX4"],
    ),
    (
        6, "Micro XRCE-DDS Agent",
        "MicroXRCEAgent v2.4.0+ installed (v2.x only — not v3.x)",
        ["MicroXRCE", "XRCE"],
    ),
    (
        7, "Environment variables",
        "Required shell variables set in ~/.bashrc",
        ["ROS_DOMAIN", "GZ_SIM_RESOURCE", "GZ_SIM_SYSTEM", "AMENT_PREFIX"],
    ),
    (
        8, "Ports available",
        "UDP ports 14540, 14550, 8888 free for use",
        ["Port"],
    ),
    (
        9, "ROS 2 workspace built",
        "ROS 2 workspace compiled with colcon",
        ["Workspace", "Package:", "colcon", "ROS 2 Workspace"],
    ),
    (
        10, "Network reachability",
        "GitHub reachable for firmware/matrix updates",
        ["Network"],
    ),
]

_STATUS_PRIORITY = {"fail": 0, "warn": 1, "pass": 2, "skip": 3}


def _step_status(results: list["CheckResult"]) -> str:
    """Collapse a list of check results into the worst single status."""
    if not results:
        return "skip"
    return min(results, key=lambda r: _STATUS_PRIORITY[r.status]).status


def _results_for_step(
    prefixes: list[str],
    all_results: list["CheckResult"],
) -> list["CheckResult"]:
    matched = []
    for r in all_results:
        for prefix in prefixes:
            if r.checker_name.startswith(prefix):
                matched.append(r)
                break
    return matched


def render_init(report: "RunReport", *, plain: bool = False) -> int:
    """Print the ordered setup guide. Returns 0/1/2 exit code (same as main)."""
    all_results = report.results
    first_fail_step: int | None = None

    rows: list[tuple[int, str, str, str, list["CheckResult"]]] = []
    for step_num, name, desc, prefixes in SETUP_STEPS:
        step_results = _results_for_step(prefixes, all_results)
        status = _step_status(step_results)

        # Mark steps that depend on a prior failed step
        if first_fail_step is not None and status != "pass":
            display_status = "skip"
            display_note = f"depends on Step {first_fail_step}"
        else:
            display_status = status
            display_note = ""
            if status == "fail" and first_fail_step is None:
                first_fail_step = step_num

        rows.append((step_num, name, desc, display_status, display_note, step_results))  # type: ignore[arg-type]

    if plain:
        _render_plain(rows)
    else:
        try:
            _render_rich(rows, report)
        except ImportError:
            _render_plain(rows)

    # Exit code based on actual (not display) statuses
    statuses = [_step_status(_results_for_step(p, all_results)) for _, _, _, p in SETUP_STEPS]
    if "fail" in statuses:
        return 2
    if "warn" in statuses:
        return 1
    return 0


def _status_label(status: str) -> str:
    return {"pass": "OK", "fail": "FAIL", "warn": "WARN", "skip": "SKIP"}.get(status, "????")


def _render_plain(rows: list) -> None:
    width = 70
    print("=" * width)
    print("  px4-sitl-doctor  —  Setup Guide")
    print("=" * width)
    print()
    for step_num, name, desc, status, note, step_results in rows:
        label = _status_label(status)
        note_str = f"  ({note})" if note else ""
        print(f"  Step {step_num:<2}  [{label:<4}]  {name}{note_str}")
        if status == "fail" and not note:
            for r in step_results:
                if r.status == "fail":
                    print(f"              Problem: {r.message}")
                    if r.fix:
                        for line in r.fix.splitlines()[:3]:
                            print(f"              FIX: {line.strip()}")
    print()
    print("=" * width)
    _print_plain_footer(rows)
    print("=" * width)


def _print_plain_footer(rows: list) -> None:
    fail_steps = [n for n, _, _, _, status, *_ in rows if status == "fail"]
    if fail_steps:
        print(f"  Fix Step(s) {', '.join(str(s) for s in fail_steps)} to proceed.")
    elif any(s == "warn" for _, _, _, _, s, *_ in rows):
        print("  Setup mostly complete — review warnings above.")
    else:
        print("  All steps complete — environment is ready for PX4 SITL!")


def _render_rich(rows: list, report: "RunReport") -> None:
    from rich.console import Console  # type: ignore[import-untyped]
    from rich.table import Table      # type: ignore[import-untyped]
    from rich.panel import Panel      # type: ignore[import-untyped]
    from rich import box              # type: ignore[import-untyped]

    console = Console()
    console.print(Panel.fit(
        "[bold cyan]px4-sitl-doctor[/bold cyan]  [dim]—  Setup Guide[/dim]\n"
        f"[dim]Platform:[/dim] {report.platform}",
        border_style="cyan",
    ))
    console.print()

    table = Table(box=box.ROUNDED, show_header=True, header_style="bold")
    table.add_column("Step", width=5, justify="right")
    table.add_column("Status", width=6)
    table.add_column("Component", width=28)
    table.add_column("Details")

    _ICONS = {"pass": "✅", "fail": "❌", "warn": "⚠️ ", "skip": "⏭ "}
    _COLORS = {"pass": "green", "fail": "red", "warn": "yellow", "skip": "dim"}

    for step_num, name, desc, status, note, step_results in rows:
        icon = _ICONS.get(status, "?")
        color = _COLORS.get(status, "white")

        if note:
            detail = f"[dim]{note}[/dim]"
        elif status in ("fail", "warn"):
            first_bad = next((r for r in step_results if r.status == status), None)
            detail = f"[{color}]{first_bad.message}[/{color}]" if first_bad else desc
        else:
            detail = f"[dim]{desc}[/dim]"

        table.add_row(
            str(step_num),
            f"{icon}",
            f"[bold]{name}[/bold]",
            detail,
        )

    console.print(table)
    console.print()

    fail_steps = [n for n, _, _, _, s, *_ in rows if s == "fail"]
    if fail_steps:
        console.print(
            f"[red bold]  Fix Step(s) {', '.join(str(s) for s in fail_steps)} before proceeding.[/red bold]"
        )
        console.print(
            "  [dim]Run [bold]px4-doctor[/bold] for detailed check output, "
            "or [bold]px4-doctor fix[/bold] to auto-apply fixes.[/dim]"
        )
    elif any(s == "warn" for _, _, _, _, s, *_ in rows):
        console.print("[yellow]  Setup mostly complete — review warnings with px4-doctor.[/yellow]")
    else:
        console.print("[green bold]  All steps complete — environment ready for PX4 SITL! 🚀[/green bold]")
    console.print()
