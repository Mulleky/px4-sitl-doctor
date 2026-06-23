# MicroXRCEAgent v3 vs v2 with PX4

One common PX4 + ROS 2 SITL failure is a MicroXRCEAgent major-version mismatch.

The symptom is confusing:

- PX4 SITL appears to start.
- Gazebo may appear to start.
- MicroXRCEAgent may start without an obvious error.
- `ros2 topic list` does not show the PX4 topics you expect.

`px4-sitl-doctor` checks this mismatch explicitly.

## Quick diagnosis

Run:

```bash
px4-doctor --only microxrce --plain
```

If the installed agent is incompatible with the PX4 client, the report will show a warning or failure with a concrete fix.

## Why this happens

PX4's embedded XRCE-DDS client and the desktop `MicroXRCEAgent` need to speak a compatible protocol. A newer agent major version can be installed on your system while the PX4 side expects an older compatible agent.

That can create a silent failure mode: the process runs, but ROS 2 topics do not appear.

## Recommended fix

If `px4-doctor` reports that MicroXRCEAgent v3 is incompatible with your PX4 setup, install or switch to a compatible v2 agent.

For snap-based installs, the fix is usually:

```bash
sudo snap install micro-xrce-dds-agent --channel=2.x/stable
```

If it is already installed:

```bash
sudo snap refresh micro-xrce-dds-agent --channel=2.x/stable
```

Then rerun:

```bash
px4-doctor --only microxrce --plain
```

## Other MicroXRCEAgent checks

The tool also checks:

- whether the `MicroXRCEAgent` binary is on `PATH`
- whether the detected version is old
- whether UDP port `8888` is available
- whether the installed version is likely to work with the current PX4 compatibility matrix

Run:

```bash
px4-doctor --only microxrce,port --verbose
```

for the full detail.

## Manual checks

Check the agent version:

```bash
MicroXRCEAgent --version
```

Check whether port `8888` is already in use:

```bash
sudo lsof -i UDP:8888
```

## Related troubleshooting

If the agent version is correct but PX4 topics still do not appear, continue with:

- [PX4 ROS 2 topics not showing](ros2-topics-not-showing.md)
- [PX4 + ROS 2 + Gazebo compatibility](px4-gazebo-ros2-compatibility.md)
