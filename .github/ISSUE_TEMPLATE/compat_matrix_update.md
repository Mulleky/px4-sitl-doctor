---
name: Compatibility Matrix Update
about: Report a new supported environment combo or deprecated one
title: "[COMPAT] <combo name or EOL distro>"
labels: compatibility
---

## Type of update

- [ ] New supported combo (test results included)
- [ ] Deprecation (EOL distro or version)
- [ ] False positive fix (checker incorrectly fails on valid combo)
- [ ] Matrix sync (version released upstream)

## Details

### For new combos:

- **OS:** Ubuntu 22.04 / 24.04 / WSL2
- **ROS 2 distro & version:**
- **Gazebo version & name:**
- **PX4 version:**
- **MicroXRCEAgent version:**

**Test results (run `px4-doctor --plain`):**
```
[paste output here]
```

**SITL smoke test:** [ ] Passed

---

### For deprecations:

- **Component:** (e.g., ROS 2 Humble)
- **EOL date:**
- **Reason:** (e.g., no longer receives security patches)

---

### For false positive fixes:

- **What was wrong:**
- **Root cause:**
- **How to verify the fix:**

## Related upstream release

Link to relevant GitHub release or announcement.
