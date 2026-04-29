"""Fix runner — collects and optionally executes fix commands from check results."""

from __future__ import annotations

import re
import subprocess
import sys
from typing import TYPE_CHECKING

import click

if TYPE_CHECKING:
    from px4_doctor.runner import RunReport
    from px4_doctor.models.result import CheckResult

# Lines starting with these tokens are treated as executable shell commands.
_EXEC_PREFIXES = (
    "sudo ", "apt ", "pip ", "pip3 ", "snap ", "source ", "export ",
    "cd ", "git ", "make ", "cmake ", "mkdir ", "cp ", "mv ", "chmod ",
    "MicroXRCEAgent", "colcon ", "ros2 ", "gz ", "python ", "python3 ",
)

_SHELL_LINE_RE = re.compile(
    r"^\s*("
    r"sudo\s.*|apt\s.*|pip3?\s.*|snap\s.*|source\s.*|export\s.*"
    r"|cd\s.*|git\s.*|make\s.*|cmake\s.*|mkdir\s.*|cp\s.*|mv\s.*|chmod\s.*"
    r"|MicroXRCEAgent.*|colcon\s.*|ros2\s.*|gz\s.*|python3?\s.*"
    r")\s*$"
)


def _extract_commands(fix_text: str) -> list[str]:
    """Return executable lines from a fix string, stripping prose."""
    cmds: list[str] = []
    for line in fix_text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if _SHELL_LINE_RE.match(stripped):
            cmds.append(stripped)
        # Also catch lines indented with 2+ spaces that look like commands
        elif line.startswith("  ") and any(stripped.startswith(p) for p in _EXEC_PREFIXES):
            cmds.append(stripped)
    return cmds


def collect_fixes(report: "RunReport") -> list[tuple["CheckResult", list[str]]]:
    """Return (result, [executable_cmd, ...]) for fail/warn results that have a fix."""
    fixes = []
    for result in report.results:
        if result.status in ("fail", "warn") and result.fix:
            cmds = _extract_commands(result.fix)
            if cmds:
                fixes.append((result, cmds))
    return fixes


def _severity_order(status: str) -> int:
    return {"fail": 0, "warn": 1}.get(status, 2)


def render_fixes_dry_run(fixes: list[tuple["CheckResult", list[str]]]) -> None:
    """Print all fix commands grouped by severity without executing."""
    if not fixes:
        click.echo("No actionable fixes found — environment looks clean.")
        return

    sorted_fixes = sorted(fixes, key=lambda t: _severity_order(t[0].status))

    failures = [(r, cmds) for r, cmds in sorted_fixes if r.status == "fail"]
    warnings = [(r, cmds) for r, cmds in sorted_fixes if r.status == "warn"]

    def _section(items: list, label: str, color: str) -> None:
        if not items:
            return
        click.echo()
        click.echo(click.style(f"  {label}", fg=color, bold=True))
        click.echo(click.style("  " + "─" * 50, fg=color))
        for result, cmds in items:
            click.echo(f"\n  [{result.checker_name}]")
            for cmd in cmds:
                click.echo(f"    {cmd}")

    click.echo(click.style("px4-doctor fix  —  dry run", bold=True))
    click.echo("The following commands would be executed (in order):")
    _section(failures, "FAILURES (fix these first)", "red")
    _section(warnings, "WARNINGS", "yellow")
    click.echo()
    click.echo("Run with --run to execute, or --run --yes to skip confirmations.")


def run_fixes(
    fixes: list[tuple["CheckResult", list[str]]],
    *,
    yes: bool = False,
) -> int:
    """Execute fix commands interactively. Returns count of commands that failed."""
    if not fixes:
        click.echo("No actionable fixes found — environment looks clean.")
        return 0

    sorted_fixes = sorted(fixes, key=lambda t: _severity_order(t[0].status))
    failed = 0

    click.echo(click.style("px4-doctor fix  —  executing fixes", bold=True))
    click.echo()

    for result, cmds in sorted_fixes:
        status_color = "red" if result.status == "fail" else "yellow"
        click.echo(click.style(f"[{result.checker_name}]", fg=status_color, bold=True))
        click.echo(f"  {result.message}")
        click.echo()

        for cmd in cmds:
            click.echo(f"  $ {cmd}")
            if not yes:
                confirmed = click.confirm("  Execute this command?", default=True)
                if not confirmed:
                    click.echo("  Skipped.")
                    continue

            try:
                proc = subprocess.run(cmd, shell=True, check=False)
                if proc.returncode != 0:
                    click.echo(
                        click.style(f"  Command exited with code {proc.returncode}", fg="red")
                    )
                    failed += 1
                else:
                    click.echo(click.style("  Done.", fg="green"))
            except Exception as exc:
                click.echo(click.style(f"  Error: {exc}", fg="red"))
                failed += 1

        click.echo()

    if failed:
        click.echo(click.style(f"{failed} command(s) failed — review output above.", fg="red"))
    else:
        click.echo(click.style("All fix commands completed successfully.", fg="green"))

    return failed
