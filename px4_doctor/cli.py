"""Click CLI entry point — px4-doctor command."""

from __future__ import annotations

import sys

import click

from px4_doctor import __version__
from px4_doctor.runner import DoctorRunner, RunOptions


# ---------------------------------------------------------------------------
# Shared option builders (reused by multiple subcommands)
# ---------------------------------------------------------------------------

def _common_run_options(fn):
    """Decorator that attaches common checker-filtering options."""
    fn = click.option("--px4-path", default=None, metavar="PATH",
                      help="Override PX4-Autopilot directory detection.")(fn)
    fn = click.option("--ws-path", default=None, metavar="PATH",
                      help="Override ROS 2 workspace directory detection.")(fn)
    fn = click.option("--offline", is_flag=True,
                      help="Skip all network checks.")(fn)
    fn = click.option("--only", default=None, metavar="CHECKER[,CHECKER]",
                      help=(
                          "Run only the named checker(s). "
                          "Names: os, python, ros2, gazebo, px4, microxrce, env, library, "
                          "port, workspace, network, wsl"
                      ))(fn)
    fn = click.option("--skip", "skip_checkers", default=None, metavar="CHECKER[,CHECKER]",
                      help="Skip the named checker(s).")(fn)
    return fn


def _build_options(only: str | None, skip_checkers: str | None,
                   px4_path: str | None, ws_path: str | None,
                   offline: bool, verbose: bool = False) -> RunOptions:
    return RunOptions(
        px4_path=px4_path,
        ws_path=ws_path,
        offline=offline,
        only=[s.strip() for s in only.split(",")] if only else [],
        skip=[s.strip() for s in skip_checkers.split(",")] if skip_checkers else [],
        verbose=verbose,
    )


# ---------------------------------------------------------------------------
# Main group
# ---------------------------------------------------------------------------

@click.group(invoke_without_command=True)
@click.pass_context
@click.option("--verbose", "-v", is_flag=True, help="Show detailed output for each check.")
@click.option("--json", "as_json", is_flag=True, help="Output results as JSON.")
@click.option("--plain", is_flag=True, help="Plain text output — no Rich formatting (good for CI).")
@click.option("--md", "as_md", is_flag=True, help="Output results as Markdown.")
@click.option("--px4-path", default=None, metavar="PATH",
              help="Override PX4-Autopilot directory detection.")
@click.option("--ws-path", default=None, metavar="PATH",
              help="Override ROS 2 workspace directory detection.")
@click.option("--offline", is_flag=True,
              help="Skip all network checks and disable remote matrix fetch.")
@click.option("--only", default=None, metavar="CHECKER[,CHECKER]",
              help=(
                  "Run only the named checker(s). "
                  "Names: os, python, ros2, gazebo, px4, microxrce, env, library, port, "
                  "workspace, network, wsl"
              ))
@click.option("--skip", "skip_checkers", default=None, metavar="CHECKER[,CHECKER]",
              help="Skip the named checker(s).")
@click.option("--update-matrix", is_flag=True,
              help="Force-fetch the latest compatibility.yaml from GitHub and save it locally.")
@click.option("--save-report", "save_report", default=None, metavar="PATH",
              help=(
                  "Save the report to a file. Format is inferred from the extension: "
                  ".json → JSON, .md → Markdown, anything else → plain text."
              ))
@click.option("--export-env", "export_env", is_flag=True,
              help=(
                  "Print missing environment variable fix commands (export/source lines) "
                  "suitable for pasting into ~/.bashrc."
              ))
@click.option("--watch", is_flag=True,
              help="Re-run all checks in a loop, refreshing the display on each cycle.")
@click.option("--interval", default=5, show_default=True, metavar="SECONDS",
              help="Seconds between refreshes when --watch is active.")
@click.version_option(__version__, "--version", prog_name="px4-doctor")
def main(
    ctx: click.Context,
    verbose: bool,
    as_json: bool,
    plain: bool,
    as_md: bool,
    px4_path: str | None,
    ws_path: str | None,
    offline: bool,
    only: str | None,
    skip_checkers: str | None,
    update_matrix: bool,
    save_report: str | None,
    export_env: bool,
    watch: bool,
    interval: int,
) -> None:
    """px4-sitl-doctor — pre-launch environment validator for PX4 + ROS 2 + Gazebo SITL.

    Run without arguments to check your full environment. Use --only or --skip to
    restrict which checks run.

    Exit codes:
      0 — all checks passed (warns are acceptable)
      1 — warnings only
      2 — one or more failures
    """
    if ctx.invoked_subcommand is not None:
        return  # let the subcommand handle it

    if update_matrix:
        _update_matrix()
        return

    options = _build_options(only, skip_checkers, px4_path, ws_path, offline, verbose)

    from px4_doctor.report import render, render_export_env, save_report_to_file

    if watch:
        _watch_loop(options, verbose, as_json, as_md, plain, interval)
        return

    runner = DoctorRunner(options)
    report = runner.run_all()

    if export_env:
        render_export_env(report)
        sys.exit(report.exit_code)

    exit_code = render(report, verbose=verbose, as_json=as_json, as_md=as_md, plain=plain)

    if save_report:
        try:
            save_report_to_file(report, save_report, verbose=verbose)
            click.echo(f"Report saved to: {save_report}")
        except OSError as exc:
            click.echo(f"ERROR: Could not save report to {save_report!r}: {exc}", err=True)

    sys.exit(exit_code)


def _watch_loop(
    options: RunOptions,
    verbose: bool,
    as_json: bool,
    as_md: bool,
    plain: bool,
    interval: int,
) -> None:
    """Continuously re-run checks and refresh the terminal display."""
    import time

    from px4_doctor.report import render

    prev_statuses: dict[str, str] = {}
    iteration = 0

    try:
        while True:
            runner = DoctorRunner(options)
            report = runner.run_all()

            click.clear()
            render(report, verbose=verbose, as_json=as_json, as_md=as_md, plain=plain)

            current_statuses = {r.checker_name: r.status for r in report.results}
            if iteration > 0 and current_statuses != prev_statuses:
                changed = {
                    name: (prev_statuses.get(name, "new"), current_statuses[name])
                    for name in current_statuses
                    if prev_statuses.get(name) != current_statuses[name]
                }
                parts = [f"{name}: {b}→{a}" for name, (b, a) in changed.items()]
                click.echo(f"\n[Watch] Changed: {', '.join(parts)}")

            prev_statuses = current_statuses
            iteration += 1
            click.echo(
                f"\n[Watch] Refreshing every {interval}s  (iteration {iteration})  "
                "— Ctrl+C to stop"
            )
            time.sleep(interval)

    except KeyboardInterrupt:
        click.echo("\n[Watch] Stopped.")
        sys.exit(0)


# ---------------------------------------------------------------------------
# Subcommand: list-combos
# ---------------------------------------------------------------------------

@main.command("list-combos")
def list_combos() -> None:
    """Print all known compatible version combinations from the matrix."""
    from px4_doctor.models.compat_matrix import CompatMatrix

    matrix = CompatMatrix()
    combos = matrix.get_combos()

    if not combos:
        click.echo("No combos found in compatibility matrix.")
        return

    try:
        from rich.console import Console  # type: ignore[import-untyped]
        from rich.table import Table      # type: ignore[import-untyped]

        console = Console()
        table = Table(title="Compatible Version Combinations", show_lines=True)
        table.add_column("Name", style="bold")
        table.add_column("ROS 2")
        table.add_column("Gazebo")
        table.add_column("PX4 Min")
        table.add_column("PX4 Max")
        table.add_column("Ubuntu")
        table.add_column("Notes")

        for c in combos:
            table.add_row(
                c.get("name", ""),
                c.get("ros2", ""),
                c.get("gazebo", ""),
                c.get("px4_min", ""),
                str(c.get("px4_max", "any")),
                ", ".join(c.get("ubuntu", [])),
                c.get("notes", ""),
            )
        console.print(table)
    except ImportError:
        click.echo(f"{'Name':<25} {'ROS 2':<10} {'Gazebo':<12} {'PX4 Min':<10} Ubuntu")
        click.echo("-" * 70)
        for c in combos:
            click.echo(
                f"{c.get('name',''):<25} {c.get('ros2',''):<10} "
                f"{c.get('gazebo',''):<12} {c.get('px4_min',''):<10} "
                f"{', '.join(c.get('ubuntu',[]))}"
            )


# ---------------------------------------------------------------------------
# Subcommand: fix
# ---------------------------------------------------------------------------

@main.command("fix")
@click.option("--run", "do_run", is_flag=True,
              help="Execute fix commands (default: dry-run only).")
@click.option("--yes", "-y", is_flag=True,
              help="Skip per-command confirmation prompts (use with --run).")
@click.option("--verbose", "-v", is_flag=True, help="Show detailed check output.")
@click.option("--plain", is_flag=True, help="Plain text output.")
@_common_run_options
def fix_cmd(
    do_run: bool,
    yes: bool,
    verbose: bool,
    plain: bool,
    px4_path: str | None,
    ws_path: str | None,
    offline: bool,
    only: str | None,
    skip_checkers: str | None,
) -> None:
    """Show (or execute) fix commands for all failing checks.

    By default this is a dry-run — it prints what would be executed.
    Use --run to actually execute the commands, --run --yes to skip confirmations.
    """
    from px4_doctor.fixer import collect_fixes, render_fixes_dry_run, run_fixes
    from px4_doctor.report import render

    options = _build_options(only, skip_checkers, px4_path, ws_path, offline, verbose)
    runner = DoctorRunner(options)
    report = runner.run_all()

    render(report, verbose=verbose, plain=plain)
    click.echo()

    fixes = collect_fixes(report)

    if do_run:
        failed = run_fixes(fixes, yes=yes)
        sys.exit(2 if failed else 0)
    else:
        render_fixes_dry_run(fixes)


# ---------------------------------------------------------------------------
# Subcommand: init
# ---------------------------------------------------------------------------

@main.command("init")
@click.option("--plain", is_flag=True, help="Plain text output — no Rich formatting.")
@_common_run_options
def init_cmd(
    plain: bool,
    px4_path: str | None,
    ws_path: str | None,
    offline: bool,
    only: str | None,
    skip_checkers: str | None,
) -> None:
    """Show an ordered setup checklist for PX4 SITL from scratch.

    Maps all check results onto a 10-step dependency-ordered guide.
    Steps after the first failure are shown as 'depends on Step N'
    so you always know exactly what to fix first.
    """
    from px4_doctor.init_guide import render_init

    options = _build_options(only, skip_checkers, px4_path, ws_path, offline)
    runner = DoctorRunner(options)
    report = runner.run_all()

    exit_code = render_init(report, plain=plain)
    sys.exit(exit_code)


# ---------------------------------------------------------------------------
# Subcommand: snap
# ---------------------------------------------------------------------------

@main.group("snap")
def snap_group() -> None:
    """Save and diff environment snapshots.

    \b
    Examples:
      px4-doctor snap save baseline.json
      px4-doctor snap diff baseline.json
    """


@snap_group.command("save")
@click.argument("path", metavar="FILE")
@_common_run_options
def snap_save(
    path: str,
    px4_path: str | None,
    ws_path: str | None,
    offline: bool,
    only: str | None,
    skip_checkers: str | None,
) -> None:
    """Run all checks and save the results to FILE as a JSON snapshot."""
    from px4_doctor.snapshot import save_snapshot

    options = _build_options(only, skip_checkers, px4_path, ws_path, offline)
    runner = DoctorRunner(options)
    report = runner.run_all()

    save_snapshot(report, path)
    click.echo(f"Snapshot saved to: {path}")
    click.echo(
        f"  {report.pass_count} passed  {report.warn_count} warnings  "
        f"{report.fail_count} failures  {report.skip_count} skipped"
    )


@snap_group.command("diff")
@click.argument("path", metavar="FILE")
@click.option("--plain", is_flag=True, help="Plain text output.")
@_common_run_options
def snap_diff(
    path: str,
    plain: bool,
    px4_path: str | None,
    ws_path: str | None,
    offline: bool,
    only: str | None,
    skip_checkers: str | None,
) -> None:
    """Compare current environment against a saved snapshot FILE."""
    from px4_doctor.snapshot import load_snapshot, render_diff

    saved = load_snapshot(path)

    options = _build_options(only, skip_checkers, px4_path, ws_path, offline)
    runner = DoctorRunner(options)
    report = runner.run_all()

    render_diff(saved, report, plain=plain)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _update_matrix() -> None:
    """Force-fetch the latest compatibility.yaml from GitHub and save to user override path."""
    try:
        import requests  # type: ignore[import-untyped]
        import yaml      # type: ignore[import-untyped]
    except ImportError:
        click.echo("ERROR: 'requests' and 'pyyaml' are required for --update-matrix.", err=True)
        sys.exit(1)

    from px4_doctor.models.compat_matrix import _GITHUB_URL, user_override_path

    click.echo(f"Fetching: {_GITHUB_URL}")
    try:
        resp = requests.get(_GITHUB_URL, timeout=10)
        resp.raise_for_status()
        data = yaml.safe_load(resp.text)
    except (requests.RequestException, yaml.YAMLError) as exc:
        click.echo(f"ERROR: Failed to fetch matrix: {exc}", err=True)
        sys.exit(1)

    dest = user_override_path()
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(resp.text, encoding="utf-8")
    except OSError as exc:
        click.echo(f"ERROR: Failed to write to {dest}: {exc}", err=True)
        sys.exit(1)

    click.echo(f"Updated: {dest}")
    version = data.get("meta", {}).get("last_updated", "unknown")
    click.echo(f"Matrix updated successfully (last_updated: {version})")


if __name__ == "__main__":
    main()
