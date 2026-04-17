# Semi-Annual Compatibility Sweep Checklist

Run this checklist each **May** (after ROS 2 release, ~May 23) and **November**.
Goal: validate all combos in `compatibility.yaml` on clean installs, add any new combos, mark deprecated ones.

---

## Metadata

| Field | Value |
|-------|-------|
| Sweep date | YYYY-MM-DD |
| Tester | |
| Triggered by | [ ] scheduled  [ ] new ROS 2 release  [ ] new Gazebo release  [ ] new PX4 release |

---

## Step 1 — Run the version check script

```bash
python scripts/check_versions.py
```

Record what's new:

| Component | Latest upstream | In matrix? |
|-----------|-----------------|------------|
| ROS 2 | | [ ] yes  [ ] no |
| Gazebo | | [ ] yes  [ ] no |
| PX4 | | [ ] yes  [ ] no |
| MicroXRCEAgent | | [ ] yes  [ ] no |

---

## Step 2 — EOL review

Check EOL status for each tracked ROS 2 distro at https://endoflife.date/ros-2

| Distro | EOL date | Still in matrix? | Action needed |
|--------|----------|-----------------|---------------|
| Humble | 2027-05 | [ ] yes | |
| Jazzy | 2029-05 | [ ] yes | |

Remove distros from `compatibility.yaml` that are past EOL and no longer receive security patches.

---

## Step 3 — Test existing combos

For each combo, spin up a **clean** Ubuntu VM or Docker container and run through the install + SITL launch.

### Combo: Humble + Harmonic (Ubuntu 22.04)

**Environment:**
- [ ] Fresh Ubuntu 22.04 VM / container
- ROS 2 version installed: ___________
- Gazebo version: ___________
- PX4 version: ___________
- MicroXRCEAgent version: ___________

**px4-doctor checks:**
```bash
pip install px4-sitl-doctor
px4-doctor --plain
```

| Check | Result |
|-------|--------|
| OS detection | [ ] pass  [ ] fail |
| ROS 2 detection | [ ] pass  [ ] fail |
| Gazebo detection | [ ] pass  [ ] fail |
| ROS2+Gazebo combo validation | [ ] pass  [ ] fail |
| PX4 detection | [ ] pass  [ ] fail |
| MicroXRCEAgent detection | [ ] pass  [ ] fail |
| Env vars | [ ] pass  [ ] fail |
| Port checks | [ ] pass  [ ] fail |

**SITL smoke test:**
```bash
cd ~/PX4-Autopilot
make px4_sitl gz_x500
# In separate terminal:
MicroXRCEAgent udp4 -p 8888
```
- [ ] PX4 SITL launched without error
- [ ] Gazebo world loaded
- [ ] MicroXRCEAgent connected
- [ ] ROS 2 topics visible (`ros2 topic list`)

Notes: ___________

---

### Combo: Jazzy + Harmonic (Ubuntu 24.04)

**Environment:**
- [ ] Fresh Ubuntu 24.04 VM / container
- ROS 2 version installed: ___________
- Gazebo version: ___________
- PX4 version: ___________
- MicroXRCEAgent version: ___________

**px4-doctor checks:**

| Check | Result |
|-------|--------|
| OS detection | [ ] pass  [ ] fail |
| ROS 2 detection | [ ] pass  [ ] fail |
| Gazebo detection | [ ] pass  [ ] fail |
| ROS2+Gazebo combo validation | [ ] pass  [ ] fail |
| PX4 detection | [ ] pass  [ ] fail |
| MicroXRCEAgent detection | [ ] pass  [ ] fail |
| Env vars | [ ] pass  [ ] fail |
| Port checks | [ ] pass  [ ] fail |

**SITL smoke test:**
- [ ] PX4 SITL launched without error
- [ ] Gazebo world loaded
- [ ] MicroXRCEAgent connected
- [ ] ROS 2 topics visible

Notes: ___________

---

### Combo: Jazzy + Ionic (Ubuntu 24.04) — Cutting-edge

**Environment:**
- [ ] Fresh Ubuntu 24.04 VM / container
- ROS 2 version installed: ___________
- Gazebo version: ___________
- PX4 version: ___________

**Notes (expect instability):**

| Check | Result |
|-------|--------|
| px4-doctor overall | [ ] pass  [ ] fail  [ ] partial |
| SITL smoke test | [ ] pass  [ ] fail  [ ] partial |

Notes: ___________

---

## Step 4 — Test new combos (if any)

If Step 1 found new distros/majors, add a section here per new combo and repeat the Step 3 template above.

New combos tested this sweep:
- [ ] (none)
- [ ] ___________

---

## Step 5 — Update compatibility.yaml

After testing, update `px4_doctor/data/compatibility.yaml`:

- [ ] Added new combo entries (with `px4_min`, `px4_max`, `python_min`, `microxrce_min`)
- [ ] Updated `notes` field on existing combos if support status changed
- [ ] Removed or marked deprecated any EOL combos
- [ ] Updated `meta.last_updated` to today's date
- [ ] Ran `python scripts/check_versions.py` again — no unexpected NEW_MAJOR remaining

---

## Step 6 — Update README table

Update the "Supported environments" table in [README.md](../README.md):

- [ ] Added new rows for new combos
- [ ] Updated status emoji for any changed combos (✅ / ⚠️ / ❌)

---

## Step 7 — Ship it

- [ ] Opened PR with `compatibility.yaml` and README changes
- [ ] Linked this checklist in the PR description
- [ ] Closed the GitHub issue opened by the version-monitor workflow (if applicable)
