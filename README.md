# px4-sitl-doctor
A pre-launch environment validator for the **PX4 + ROS 2 + Gazebo SITL** stack.

Setting up PX4 SITL with Gazebo and ROS 2 requires exact version matches across six or more software components. Mismatches produce cryptic runtime errors. `px4-sitl-doctor` catches those mismatches **before** you launch and tells you exactly what to run to fix them.

px4-sitl-doctor validates your PX4 + ROS 2 + Gazebo SITL environment in seconds. 
Detects version mismatches, missing binaries, broken env vars, and port conflicts 
before simulation launch. Runs on Ubuntu 22/24, Windows WSL2. Zero dependencies beyond 
Python 3.10+. 12 modular checks, colour output, JSON export, CI-friendly exit codes.

## Install

```bash
pip install px4-sitl-doctor
```

Or with pipx (recommended for system-wide use):

```bash
pipx install px4-sitl-doctor
```

## Usage

```bash
px4-doctor
```

That's it. The tool auto-detects your platform and runs all applicable checks.

## Example output

```
╔══════════════════════════════════════════════════════════════╗
║            px4-sitl-doctor  v0.1.0                          ║
║         Platform: ubuntu_22_04                              ║
╚══════════════════════════════════════════════════════════════╝

── OS & Python ─────────────────────────────────────────────────
✅  OS Version          Ubuntu 22.04 — supported
✅  Python Version      3.10.12 — OK
⚠️   Virtual Env        No venv active — system Python in use

── ROS 2 ───────────────────────────────────────────────────────
✅  ROS 2 Distro        humble detected
✅  ROS 2 Sourced       AMENT_PREFIX_PATH is set
❌  ROS_DISTRO Mismatch ROS_DISTRO=iron but binary reports humble
   FIX: source /opt/ros/humble/setup.bash

── Gazebo ──────────────────────────────────────────────────────
✅  Gazebo Binary       gz 8.6.0 (Harmonic) found
✅  ROS2+Gazebo Combo   humble + harmonic — compatible
❌  Camera Plugin       libGstCameraSystem.so not found
   FIX: cd ~/PX4-Autopilot && make px4_sitl gz_x500_mono_cam

SUMMARY:  18 passed   2 warnings   1 failure
Your environment has issues that will prevent SITL launch.
```

## What it checks

| Check | Description | Platforms |
|-------|-------------|-----------|
| OS Version | Ubuntu 22.04 / 24.04 or WSL2 | All |
| Python Version | Python >= 3.10 | All |
| ROS 2 | Distro detection, sourcing, version | Linux / WSL2 |
| Gazebo | Binary, version, ROS2 combo | Linux / WSL2 |
| PX4 Autopilot | Repo detection, version, SITL build | Linux / WSL2 |
| MicroXRCEAgent | Binary, version, port 8888 | Linux / WSL2 |
| Environment Vars | GZ_SIM_*, ROS_DOMAIN_ID, AMENT_PREFIX_PATH | All |
| Shared Libraries | libGstCameraSystem.so, libgps.so | Linux / WSL2 |
| Port Availability | UDP 14540, 14541, 8888, 7447 | All |
| ROS 2 Workspace | install/, px4_msgs, px4_ros_com | Linux / WSL2 |
| Network | Internet, GitHub, PyPI reachability | All |
| WSL2 | WSL2 kernel, X11, systemd, memory | WSL2 only |

## Options

| Flag | Description |
|------|-------------|
| `--verbose` / `-v` | Show detailed output for each check |
| `--json` | Output results as JSON (for scripting) |
| `--plain` | Plain text output, no colors (for CI) |
| `--md` | Output results as Markdown |
| `--px4-path PATH` | Override PX4-Autopilot directory |
| `--ws-path PATH` | Override ROS 2 workspace directory |
| `--offline` | Skip network-based checks (matrix is loaded locally by default regardless) |
| `--only CHECKER[,...]` | Run only named checker(s) |
| `--skip CHECKER[,...]` | Skip named checker(s) |
| `--update-matrix` | Fetch latest compatibility rules from GitHub |
| `--version` | Print version and exit |

Checker names: `os`, `python`, `ros2`, `gazebo`, `px4`, `microxrce`, `env`, `library`, `port`, `workspace`, `network`, `wsl`

## Subcommands

```bash
px4-doctor list-combos   # Print all known compatible version combinations
```

## Exit codes

| Code | Meaning |
|------|---------|
| 0 | All checks passed |
| 1 | Warnings only |
| 2 | One or more failures |

## Updating the compatibility rules

```bash
px4-doctor --update-matrix
```

This fetches the latest `compatibility.yaml` from GitHub and writes it to a user-writable location — `$XDG_DATA_HOME/px4-doctor/compatibility.yaml` (defaults to `~/.local/share/px4-doctor/compatibility.yaml`). Subsequent runs prefer this override over the bundled copy, so pip-installed and wheel-installed users get fresh rules without reinstalling or needing write access to the package directory.

Normal `px4-doctor` runs do **not** touch the network — matrix loading is local-only by default for fast, offline-safe startup. Use `--update-matrix` explicitly when you want the latest rules.

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

**Want to help?** We welcome bug reports, feature requests, and code contributions. Here's how to get started:

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

