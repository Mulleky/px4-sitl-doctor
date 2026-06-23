# PX4 + ROS 2 + Gazebo compatibility

PX4 SITL depends on several components lining up at the same time:

- Ubuntu version
- ROS 2 distro
- Gazebo release
- PX4 version
- MicroXRCEAgent version
- PX4 Gazebo plugins
- ROS 2 workspace packages

When one piece is mismatched, the failure may appear much later as a Gazebo crash, missing ROS 2 topics, missing plugins, or a PX4 launch that starts but does not communicate correctly.

`px4-sitl-doctor` checks the known-good combinations before launch.

## Quick compatibility check

Install:

```bash
pipx install px4-sitl-doctor
```

Run:

```bash
px4-doctor --only os,ros2,gazebo,px4,microxrce --plain
```

To see the compatibility table:

```bash
px4-doctor list-combos
```

## Known supported combinations

The bundled compatibility matrix tracks tested combinations such as:

| OS | ROS 2 | Gazebo | PX4 | Status |
|----|-------|--------|-----|--------|
| Ubuntu 22.04 | Humble | Harmonic | >= 1.14.0 | Recommended |
| Ubuntu 24.04 | Jazzy | Harmonic | >= 1.15.0 | Supported |
| Ubuntu 24.04 | Jazzy | Ionic | >= 1.15.0 | Cutting-edge |
| Windows 10/11 WSL2 | via WSL2 | via WSL2 | via WSL2 | Supported |

Run the local command for the authoritative list shipped with your installed version:

```bash
px4-doctor list-combos
```

## Update the matrix

If PX4, ROS 2, Gazebo, or MicroXRCEAgent has released a newer version, update the local compatibility rules:

```bash
px4-doctor --update-matrix
```

Then rerun:

```bash
px4-doctor
```

Normal `px4-doctor` runs are local and offline-safe. The matrix is only fetched when you explicitly use `--update-matrix`.

## Common compatibility failures

### ROS 2 and Gazebo mismatch

Example problem:

- ROS 2 Humble with a newer Gazebo release that is not in the validated matrix
- ROS 2 Jazzy with an older Gazebo setup

Run:

```bash
px4-doctor --only ros2,gazebo --plain
```

### PX4 build missing Gazebo plugins

If `libGstCameraSystem.so` or other PX4 Gazebo plugins are missing, build the relevant PX4 target:

```bash
cd ~/PX4-Autopilot
make px4_sitl gz_x500
```

For camera SITL:

```bash
cd ~/PX4-Autopilot
make px4_sitl gz_x500_mono_cam
```

Then rerun:

```bash
px4-doctor --only gazebo,library,env --plain
```

### Environment variables missing

PX4 Gazebo SITL often needs:

```bash
export GZ_SIM_RESOURCE_PATH=$HOME/PX4-Autopilot/Tools/simulation/gz/models
export GZ_SIM_SYSTEM_PLUGIN_PATH=$HOME/PX4-Autopilot/build/px4_sitl_default/lib
```

Use:

```bash
px4-doctor --export-env
```

to print the environment lines the tool thinks are missing.

## CI usage

For CI or reproducible setup checks:

```bash
px4-doctor --plain --offline --only os,python,ros2,gazebo,px4,microxrce
```

The exit code can be used to fail the job:

| Code | Meaning |
|------|---------|
| 0 | all checks passed |
| 1 | warnings only |
| 2 | one or more failures |

## Related troubleshooting

- [PX4 ROS 2 topics not showing](ros2-topics-not-showing.md)
- [MicroXRCEAgent v3 vs v2](microxrceagent-v3-vs-v2.md)
