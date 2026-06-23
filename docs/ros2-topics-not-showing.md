# PX4 ROS 2 topics not showing

If PX4 SITL starts but `ros2 topic list` does not show PX4 topics, the problem is usually not ROS 2 itself. It is usually one of these:

- MicroXRCEAgent is not running.
- MicroXRCEAgent is the wrong major version.
- ROS 2 was not sourced in the current terminal.
- PX4 is not publishing through the expected XRCE-DDS bridge.
- UDP port `8888` is already in use.
- The ROS 2 workspace containing `px4_msgs` or `px4_ros_com` was not built or sourced.

`px4-sitl-doctor` checks these conditions before you spend time debugging PX4 launch output.

## Quick check

Install the tool:

```bash
pipx install px4-sitl-doctor
```

Run only the checks related to ROS 2 and MicroXRCE-DDS:

```bash
px4-doctor --only ros2,microxrce,workspace,port --plain
```

For more detail:

```bash
px4-doctor --only ros2,microxrce,workspace,port --verbose
```

## Expected working setup

For a normal PX4 + ROS 2 + Gazebo SITL setup, the tool should find:

- a supported ROS 2 distro, such as Humble or Jazzy
- `ROS_DISTRO` set correctly
- `AMENT_PREFIX_PATH` set
- `MicroXRCEAgent` installed
- UDP port `8888` available
- `px4_msgs` and `px4_ros_com` available in a sourced workspace, when required

## Common fixes

### Source ROS 2

If `ros2` is not found or `ROS_DISTRO` is missing:

```bash
source /opt/ros/humble/setup.bash
```

For Jazzy:

```bash
source /opt/ros/jazzy/setup.bash
```

To persist it:

```bash
echo 'source /opt/ros/humble/setup.bash' >> ~/.bashrc
```

Use the distro that is actually installed on your system.

### Source your workspace

If your workspace has already been built:

```bash
source ~/ros2_ws/install/local_setup.bash
```

If it has not been built:

```bash
cd ~/ros2_ws
colcon build --symlink-install
source install/local_setup.bash
```

### Check MicroXRCEAgent

PX4 uses XRCE-DDS to bridge uORB data into ROS 2. If the agent is missing or incompatible, PX4 can appear to run normally while ROS 2 topics never appear.

Run:

```bash
px4-doctor --only microxrce --plain
```

See [MicroXRCEAgent v2 vs v3](microxrceagent-v3-vs-v2.md) for the most common version mismatch.

### Check port 8888

MicroXRCEAgent usually uses UDP port `8888`.

```bash
px4-doctor --only port --plain
```

To inspect manually:

```bash
sudo lsof -i UDP:8888
```

If another process is using it, stop that process before starting the agent.

## Why `ros2 topic list` can be empty

`ros2 topic list` only shows PX4 topics after the ROS 2 side can see data from PX4. A successful Gazebo launch does not guarantee that the ROS 2 bridge is working. PX4, Gazebo, ROS 2, `px4_msgs`, `px4_ros_com`, MicroXRCEAgent, and the relevant environment variables all need to line up.

Use:

```bash
px4-doctor
```

to check the complete environment.

## Still stuck?

Open an issue with:

```bash
px4-doctor --verbose --plain
```

and include your OS, ROS 2 distro, Gazebo version, PX4 version, and MicroXRCEAgent version.
