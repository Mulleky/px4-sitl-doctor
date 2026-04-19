"""Click CLI entry point — px4-doctor command."""

from __future__ import annotations

import sys

import click

from px4_doctor import __version__
from px4_doctor.runner import DoctorRunner, RunOptions


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

    options = RunOptions(
        px4_path=px4_path,
        ws_path=ws_path,
        offline=offline,
        only=[s.strip() for s in only.split(",")] if only else [],
        skip=[s.strip() for s in skip_checkers.split(",")] if skip_checkers else [],
        verbose=verbose,
    )

    runner = DoctorRunner(options)
    report = runner.run_all()

    from px4_doctor.report import render
    exit_code = render(
        report,
        verbose=verbose,
        as_json=as_json,
        as_md=as_md,
        plain=plain,
    )
    sys.exit(exit_code)


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
        # Plain fallback
        click.echo(f"{'Name':<25} {'ROS 2':<10} {'Gazebo':<12} {'PX4 Min':<10} Ubuntu")
        click.echo("-" * 70)
        for c in combos:
            click.echo(
                f"{c.get('name',''):<25} {c.get('ros2',''):<10} "
                f"{c.get('gazebo',''):<12} {c.get('px4_min',''):<10} "
                f"{', '.join(c.get('ubuntu',[]))}"
            )


def _update_matrix() -> None:
    """Force-fetch the latest compatibility.yaml from GitHub and save it to the
    user-writable override path. The bundled copy is never modified — this keeps
    --update-matrix working identically across pip-installed, wheel, and editable
    installs.
    """
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
