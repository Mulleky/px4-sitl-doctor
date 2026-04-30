# px4-sitl-doctor

A pre-launch environment validator for the **PX4 + ROS 2 + Gazebo SITL** stack.

Setting up PX4 SITL with Gazebo and ROS 2 requires exact version matches across six or more software components. Mismatches produce cryptic runtime errors. `px4-sitl-doctor` catches those mismatches **before** you launch and tells you exactly what to run to fix them — or fixes them for you.

## Install

```bash
pip install px4-sitl-doctor
```

Or with pipx (recommended for system-wide use):

```bash
pipx install px4-sitl-doctor
```

## Quick start

```bash
# Run all checks
px4-doctor

# See an ordered setup guide (great for first-time setup)
px4-doctor init

# Auto-apply all fixes in one command
px4-doctor fix --run
```

## Example output

```
╭─────────────────────────────────────────╮
│  px4-sitl-doctor  v0.3.0               │
│  Platform: ubuntu_22_04                │
╰─────────────────────────────────────────╯

── OS & Python ──────────────────────────────────────
✅  OS Version          Ubuntu 22.04 — supported
✅  Python Version      3.10.12 — OK
⚠️   Virtual Env        No venv active — system Python in use

── ROS 2 ────────────────────────────────────────────
✅  ROS 2 Distro        humble detected
✅  ROS 2 Sourced       AMENT_PREFIX_PATH is set

── MicroXRCE-DDS ────────────────────────────────────
⚠️   MicroXRCEAgent     v3.0.0 detected — INCOMPATIBLE with PX4's v2.x client
    FIX: sudo snap install micro-xrce-dds-agent --channel=2.x/stable

SUMMARY:  18 passed   2 warnings   0 failures
```

## What it checks

| Check | Description | Platforms |
|-------|-------------|-----------|
| OS Version | Ubuntu 22.04 / 24.04 or WSL2 | All |
| Python Version | Python >= 3.10 | All |
| ROS 2 | Distro detection, sourcing, version | Linux / WSL2 |
| Gazebo | Binary, version, ROS2 combo | Linux / WSL2 |
| PX4 Autopilot | Repo detection, version, SITL build | Linux / WSL2 |
| MicroXRCEAgent | Binary, version (v2/v3 mismatch), port 8888 | Linux / WSL2 |
| Environment Vars | GZ_SIM_*, ROS_DOMAIN_ID, AMENT_PREFIX_PATH | All |
| Shared Libraries | libGstCameraSystem.so, libgps.so | Linux / WSL2 |
| Port Availability | UDP 14540, 14541, 14550 (QGC), 8888, 7447 | All |
| ROS 2 Workspace | install/, px4_msgs, px4_ros_com, colcon | Linux / WSL2 |
| Network | Internet, GitHub, PyPI reachability | All |
| WSL2 | WSL2 kernel, X11, systemd, memory | WSL2 only |

## Commands

### `px4-doctor` — full environment check

```bash
px4-doctor                          # run all checks
px4-doctor --only ros2,microxrce    # run specific checks only
px4-doctor --skip network           # skip specific checks
px4-doctor --offline                # skip all network checks
px4-doctor --json                   # output as JSON (for scripting)
px4-doctor --plain                  # plain text output, no colors (CI-friendly)
px4-doctor --save-report report.md  # save report to file (.json, .md, or .txt)
```

### `px4-doctor init` — ordered setup guide

Shows a 10-step ordered setup checklist. Steps after the first failure are shown as "depends on Step N" — so you always know what to fix first, in the right order.

```bash
px4-doctor init
```

```
  Step 1   [OK]    Operating System           Ubuntu 22.04 detected
  Step 2   [OK]    Python                     Python 3.11.9
  Step 3   [FAIL]  ROS 2 installed & sourced  AMENT_PREFIX_PATH not set
                   FIX: source /opt/ros/humble/setup.bash
  Step 4   [SKIP]  Gazebo simulator           depends on Step 3
  ...
```

Perfect for first-time PX4 SITL setup — stops you from debugging step 6 when step 3 is what's actually broken.

### `px4-doctor fix` — auto-fix mode

Reads fix commands from every failing check and presents them for execution.

```bash
px4-doctor fix              # dry run: show what would be executed
px4-doctor fix --run        # execute with y/N confirmation per command
px4-doctor fix --run --yes  # fully automated (good for CI)
```

Use `--only` or `--skip` to target specific checks:

```bash
px4-doctor fix --only ros2,microxrce --run
```

### `px4-doctor snap` — environment snapshots

Save a snapshot of your current environment and compare against it later to see what changed — or catch regressions.

```bash
px4-doctor snap save baseline.json      # save current state
px4-doctor snap diff baseline.json      # compare against saved state
```

```
Snapshot taken : 2026-04-28T10:00:00  (3 hours ago)

Changes since snapshot:
  ROS 2 Binary         fail  →  pass   (fixed!)
  AMENT_PREFIX_PATH    fail  →  pass   (fixed!)
  MicroXRCEAgent       fail  →  fail   (still broken)
```

Useful for "it was working yesterday" debugging, or for team members to share a known-good baseline.

### `px4-doctor list-combos` — compatible version table

```bash
px4-doctor list-combos
```

Prints all known compatible version combinations (ROS 2 distro × Gazebo × PX4 × Ubuntu).

### `--watch` — live re-check mode

Re-runs all checks on a loop. Shows what changed between iterations — great when you're actively fixing issues and want to see checks go green in real time.

```bash
px4-doctor --watch                  # refresh every 5 seconds (default)
px4-doctor --watch --interval 10    # refresh every 10 seconds
px4-doctor --watch --only ros2,microxrce  # watch specific checks only
```

Press **Ctrl+C** to stop.

### `--export-env` — print missing env commands

Scans failing environment checks and prints the exact `export` and `source` lines you need to add to `~/.bashrc`.

```bash
px4-doctor --export-env
# Output:
# Add these lines to ~/.bashrc (or run them in your current shell):

source /opt/ros/humble/setup.bash
export ROS_DOMAIN_ID=0
```

Copy-paste into `~/.bashrc` or run directly in your terminal.

## All flags

| Flag | Description |
|------|-------------|
| `--verbose` / `-v` | Show detailed output for each check |
| `--json` | Output results as JSON (for scripting) |
| `--plain` | Plain text output, no colors (for CI) |
| `--md` | Output results as Markdown |
| `--px4-path PATH` | Override PX4-Autopilot directory detection |
| `--ws-path PATH` | Override ROS 2 workspace directory detection |
| `--offline` | Skip all network-based checks |
| `--only CHECKER[,...]` | Run only named checker(s) |
| `--skip CHECKER[,...]` | Skip named checker(s) |
| `--save-report PATH` | Save report to file (`.json`, `.md`, or plain text) |
| `--export-env` | Print missing `export`/`source` lines for `~/.bashrc` |
| `--watch` | Re-run checks in a loop, show diffs |
| `--interval N` | Seconds between `--watch` refreshes (default: 5) |
| `--update-matrix` | Fetch latest compatibility rules from GitHub |
| `--version` | Print version and exit |

Checker names for `--only` / `--skip`: `os`, `python`, `ros2`, `gazebo`, `px4`, `microxrce`, `env`, `library`, `port`, `workspace`, `network`, `wsl`

## Exit codes

| Code | Meaning |
|------|---------|
| 0 | All checks passed |
| 1 | Warnings only |
| 2 | One or more failures |

These codes make `px4-doctor` easy to use in CI pipelines:

```yaml
# .github/workflows/check-env.yml
- name: Validate PX4 SITL environment
  run: px4-doctor --plain --offline --only os,python,ros2,gazebo
```

## MicroXRCE-DDS v2 vs v3

A common silent failure: Agent v3.x is **protocol-incompatible** with PX4's embedded XRCE-DDS client (which uses v2.x). The agent starts without errors, but ROS 2 topics never appear in `ros2 topic list`.

`px4-doctor` detects this explicitly and tells you how to downgrade:

```
⚠️  MicroXRCEAgent 3.0.0 — PX4's embedded XRCE-DDS client uses v2.x — INCOMPATIBLE
    FIX: sudo snap install micro-xrce-dds-agent --channel=2.x/stable
```

## Updating the compatibility rules

```bash
px4-doctor --update-matrix
```

Fetches the latest `compatibility.yaml` from GitHub and writes it to `~/.local/share/px4-doctor/compatibility.yaml`. Subsequent runs prefer this override over the bundled copy — so pip-installed users get fresh rules without reinstalling.

Normal runs do **not** touch the network by default.

## Supported environments

| OS | ROS 2 | Gazebo | PX4 | Status |
|----|-------|--------|-----|--------|
| Ubuntu 22.04 | Humble | Harmonic | >= 1.14.0 | ✅ Recommended |
| Ubuntu 24.04 | Jazzy | Harmonic | >= 1.15.0 | ✅ Supported |
| Ubuntu 24.04 | Jazzy | Ionic | >= 1.15.0 | ⚠️ Cutting-edge |
| Windows 10/11 WSL2 | (via WSL2) | (via WSL2) | (via WSL2) | ✅ Supported |
| Windows 10/11 native | — | — | — | ⚠️ Port/Python checks only |

## Troubleshooting

See [DEBUGGING.md](DEBUGGING.md) for a full guide covering:
- Tool not found / command not found
- Windows native — most checks skipped
- ROS 2, Gazebo, MicroXRCEAgent, PX4, Workspace issues
- Port conflicts and environment variable problems
- Running specific checks only

## Contributing

**Want to help?** We welcome bug reports, feature requests, and code contributions.

### Report a bug

Found a false positive or false negative? [Open a bug report](../../issues/new?template=bug_report.md) with:
- Output of `px4-doctor --json`
- Your environment (OS, Python, ROS 2, Gazebo, PX4 versions)

### Request a feature

Have an idea for a new check or improvement? [Open a feature request](../../issues/new?template=feature_request.md).

### Contribute code

Adding a new checker? Fixing a bug? Read [CONTRIBUTING.md](CONTRIBUTING.md) for the development workflow, then:

1. Fork this repo
2. Create a feature branch: `git checkout -b my-feature`
3. Add tests in `tests/test_my_check.py`
4. Run `pytest tests/ -v` to verify
5. [Open a PR](../../compare) with your changes

**Note:** We use branch protection on `main` — all changes go through pull requests.

### Security issues

Found a security vulnerability? **Do not** open a public issue. Email [carlostorresada@gmail.com](mailto:carlostorresada@gmail.com) with `[SECURITY]` in the subject line. See our [Security Policy](.github/SECURITY.md) for details.

### Code of Conduct

We follow the [Contributor Covenant](CODE_OF_CONDUCT.md). Be respectful and inclusive.

## License

MIT — see [LICENSE](LICENSE).
