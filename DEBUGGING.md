# px4-sitl-doctor — Debugging Guide

This guide covers how to interpret and act on `px4-doctor` output, fix the most common failures, and diagnose issues with the tool itself.

---

## Table of contents

- [Tool not found / not running](#tool-not-found--not-running)
- [Windows native — most checks skipped](#windows-native--most-checks-skipped)
- [Reading the output](#reading-the-output)
- [ROS 2 issues](#ros-2-issues)
- [Gazebo issues](#gazebo-issues)
- [MicroXRCEAgent issues](#microxrceagent-issues)
- [PX4 Autopilot issues](#px4-autopilot-issues)
- [Workspace issues](#workspace-issues)
- [Port conflicts](#port-conflicts)
- [Environment variable issues](#environment-variable-issues)
- [Running specific checks only](#running-specific-checks-only)

---

## Tool not found / not running

### `px4-doctor: command not found`

The Python Scripts directory is not on your PATH. Three ways to run the tool:

**Option 1 — Python module (no PATH needed)**
```bash
python -m px4_doctor --plain
```

**Option 2 — Full path to the installed script**
```
C:\Users\YOUR_USERNAME\AppData\Roaming\PythonXYZ\Scripts\px4-doctor.exe --plain
```
Replace `XYZ` with your Python version number (e.g. `Python314`).

**Option 3 — Add Scripts to PATH permanently (Windows)**
```cmd
setx PATH "%PATH%;C:\Users\YOUR_USERNAME\AppData\Roaming\PythonXYZ\Scripts"
```
Open a **new** terminal after running `setx` — the change does not apply to the current window.

**Option 3 — Add Scripts to PATH permanently (Linux / WSL2)**
```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

---

### `python -m px4_doctor` produces no output

Ensure you are running version `0.1.1` or later, which added `__main__.py`. Check your installed version:
```bash
python -m pip show px4-sitl-doctor
```
If outdated:
```bash
pip install --upgrade px4-sitl-doctor
```

---

## Windows native — most checks skipped

If the tool reports:
```
[SKIP]  ROS 2   — Windows native Python detected. Run inside WSL2.
[SKIP]  Gazebo  — Windows native Python detected. Run inside WSL2.
```

This is **expected**. PX4 SITL with ROS 2 and Gazebo requires Linux. On Windows, only env var and port checks run.

To run the full check suite, enter your WSL2 Ubuntu instance:
```bash
wsl
pip install px4-sitl-doctor
px4-doctor --plain
```

---

## Reading the output

Each check line starts with a status indicator:

| Symbol | Plain text | Meaning |
|--------|------------|---------|
| ✅ | `[PASS]` | Check passed — no action needed |
| ⚠️ | `[WARN]` | Works but could be cleaner — read the FIX suggestion |
| ❌ | `[FAIL]` | Will likely prevent SITL launch — fix before running |
| ⏭️ | `[SKIP]` | Not applicable on this platform |

Exit codes:

| Code | Meaning |
|------|---------|
| `0` | All checks passed |
| `1` | Warnings only (SITL may still work) |
| `2` | One or more failures |

Use `--verbose` to see the full detail message for every check:
```bash
px4-doctor --verbose --plain
```

---

## ROS 2 issues

### `'ros2' binary not found on PATH`

ROS 2 is not sourced in the current shell.
```bash
source /opt/ros/humble/setup.bash   # or jazzy, iron, etc.
# Add to ~/.bashrc to persist:
echo 'source /opt/ros/humble/setup.bash' >> ~/.bashrc
```

---

### `Could not determine ROS 2 distro from binary or environment`

ROS 2 Jazzy and newer no longer include the distro name in `ros2 --version` output. The tool falls back to `ROS_DISTRO` + `/opt/ros/<distro>` on disk. If both are missing:

```bash
# Check what's installed
ls /opt/ros/

# Source the correct distro
source /opt/ros/jazzy/setup.bash

# Persist it
echo 'source /opt/ros/jazzy/setup.bash' >> ~/.bashrc
```

---

### `ROS_DISTRO env var is not set`

```bash
source /opt/ros/humble/setup.bash
```
This sets `ROS_DISTRO` automatically. Add to `~/.bashrc` to avoid repeating it.

---

### `ROS_DISTRO='humble' but detected distro is 'jazzy' — mismatch`

You have sourced a different ROS 2 version than what is active. Start a clean shell and source only one distro:
```bash
exec bash
source /opt/ros/jazzy/setup.bash
```

---

### `AMENT_PREFIX_PATH not set`

Your ROS 2 workspace or base install is not sourced.
```bash
source /opt/ros/humble/setup.bash        # base install
source ~/ros2_ws/install/local_setup.bash  # workspace (if applicable)
```

---

## Gazebo issues

### `Gazebo binary ('gz' or 'ign') not found on PATH`

```bash
# Install Gazebo Harmonic (recommended for Ubuntu 22.04 + Humble or 24.04 + Jazzy)
sudo apt install gz-harmonic

# Or follow the official guide:
# https://gazebosim.org/docs/harmonic/install
```

---

### `ROS2 + Gazebo Combo is NOT a known-compatible combination`

Only these combinations are tested and supported:

| ROS 2 | Gazebo | Ubuntu |
|-------|--------|--------|
| Humble | Harmonic | 22.04, 24.04 |
| Jazzy | Harmonic | 24.04 |
| Jazzy | Ionic | 24.04 |

Mixing other versions (e.g. Humble + Ionic) is likely to cause build errors or runtime crashes.

---

### `GZ_SIM_RESOURCE_PATH is not set and default path not found`

PX4's Gazebo models directory does not exist. Build PX4 first:
```bash
cd ~/PX4-Autopilot
make px4_sitl gz_x500
```
Then add to `~/.bashrc`:
```bash
export GZ_SIM_RESOURCE_PATH=$HOME/PX4-Autopilot/Tools/simulation/gz/models
```

---

### `GZ_SIM_SYSTEM_PLUGIN_PATH is not set and default path not found`

PX4's Gazebo plugin directory does not exist. Build PX4 SITL first:
```bash
cd ~/PX4-Autopilot
make px4_sitl gz_x500
```
Then add to `~/.bashrc`:
```bash
export GZ_SIM_SYSTEM_PLUGIN_PATH=$HOME/PX4-Autopilot/build/px4_sitl_default/lib
```

---

### `GZ_SIM_* is in ~/.bashrc but not active — restart your terminal`

The variable is defined but you opened this terminal before the line was added, so it was never exported into this shell session.
```bash
source ~/.bashrc
```

---

### `libGstCameraSystem.so not found — camera SITL will not work`

The camera Gazebo plugin is only built when you compile the camera-specific SITL target:
```bash
cd ~/PX4-Autopilot
make px4_sitl gz_x500_mono_cam
```

---

## MicroXRCEAgent issues

### `MicroXRCEAgent binary not found on PATH`

```bash
# Easiest — snap package:
sudo snap install micro-xrce-dds-agent

# Or build from source:
# https://micro-xrce-dds.docs.eprosima.com/en/latest/installation.html
```

---

### `MicroXRCEAgent X.Y.Z is older than minimum 2.4.0`

```bash
sudo snap refresh micro-xrce-dds-agent
```
Or rebuild from source targeting the latest release.

---

### `UDP port 8888 is already in use — MicroXRCEAgent cannot start`

Another process is holding the port:
```bash
sudo lsof -i UDP:8888
# Kill the process shown, then recheck:
px4-doctor --only microxrce --plain
```

---

## PX4 Autopilot issues

### `PX4-Autopilot directory not found`

The tool looks for `~/PX4-Autopilot`. If your clone is elsewhere:
```bash
px4-doctor --px4-path /path/to/PX4-Autopilot --plain
```

---

### `SITL build not found (px4_sitl_default)`

You need to build PX4 at least once:
```bash
cd ~/PX4-Autopilot
make px4_sitl gz_x500
```

---

## Workspace issues

### `No ROS 2 workspace found`

The tool searches `~/ros2_ws`, `~/colcon_ws`, `~/px4_ros_com_ros2`, and the current directory. If your workspace is elsewhere:
```bash
px4-doctor --ws-path /path/to/your/workspace --plain
```

---

### `Workspace not colcon-built (no install/)`

```bash
cd ~/ros2_ws
colcon build --symlink-install
source install/local_setup.bash
```
If `px4_msgs` and `px4_ros_com` are already installed system-wide via apt, SITL may still work — the tool will downgrade this to a warning rather than a failure.

---

### `px4_msgs / px4_ros_com NOT installed`

Clone and build the required packages:
```bash
cd ~/ros2_ws/src
git clone https://github.com/PX4/px4_msgs.git
git clone https://github.com/PX4/px4_ros_com.git
cd ~/ros2_ws
colcon build --symlink-install
source install/local_setup.bash
```

---

## Port conflicts

The following UDP ports must be free before launching SITL:

| Port | Used by |
|------|---------|
| 8888 | MicroXRCEAgent (XRCE-DDS) |
| 14540 | MAVLink (vehicle 1) |
| 14541 | MAVLink (vehicle 2, multi-drone) |
| 7447 | Fast-DDS RTPS discovery |

To find what is using a port:
```bash
sudo lsof -i UDP:<port>
# or
sudo ss -ulpn | grep <port>
```

Run only port checks:
```bash
px4-doctor --only port --plain
```

---

## Environment variable issues

### All env vars showing WARN or FAIL

You likely opened a fresh terminal without sourcing your ROS 2 environment. Add these to `~/.bashrc`:
```bash
source /opt/ros/humble/setup.bash          # or jazzy
source ~/ros2_ws/install/local_setup.bash  # if using a colcon workspace
export GZ_SIM_RESOURCE_PATH=$HOME/PX4-Autopilot/Tools/simulation/gz/models
export GZ_SIM_SYSTEM_PLUGIN_PATH=$HOME/PX4-Autopilot/build/px4_sitl_default/lib
export ROS_DOMAIN_ID=0                     # optional but recommended
```
Then reload:
```bash
source ~/.bashrc
```

---

## Running specific checks only

Run a single category to focus on one area:
```bash
px4-doctor --only ros2 --plain
px4-doctor --only gazebo --plain
px4-doctor --only port --plain
px4-doctor --only env --plain
```

Skip a category you know is fine:
```bash
px4-doctor --skip network --plain   # skip if offline
```

Available checker names: `os`, `python`, `ros2`, `gazebo`, `px4`, `microxrce`, `env`, `library`, `port`, `workspace`, `network`, `wsl`

---

## Still stuck?

Open an issue at **https://github.com/Mulleky/px4-sitl-doctor/issues** and include the output of:
```bash
px4-doctor --verbose --plain
```
