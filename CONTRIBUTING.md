# Contributing to px4-sitl-doctor

## Adding a new checker

1. Create `px4_doctor/checkers/my_check.py`
2. Subclass `BaseChecker` and implement `run() -> list[CheckResult]`
3. Set `.name`, `.category`, and `.platforms` class attributes
4. Inject any shared context (matrix, platform) via `__init__`
5. Add your checker to the list in `runner.py` `_build_checkers()`
6. Register the shortname in `_CHECKER_SHORTNAMES` in `runner.py`
7. Add tests in `tests/test_my_check.py`
8. Open a PR

### Minimal checker template

```python
from px4_doctor.checkers.base import BaseChecker
from px4_doctor.models.result import CheckResult
from px4_doctor.platform_utils import detect_platform

class MyChecker(BaseChecker):
    name = "My Check"
    category = "core"          # core | env | network | workspace
    platforms = ["all"]        # or e.g. ["ubuntu_22_04", "ubuntu_24_04"]

    def __init__(self, matrix=None):
        self._matrix = matrix
        self._platform = detect_platform()

    def run(self) -> list[CheckResult]:
        results = []
        # ... your checks ...
        results.append(CheckResult(
            checker_name=self.name,
            status="pass",          # pass | warn | fail | skip
            message="Everything OK",
            fix=None,
        ))
        return results
```

## Updating the compatibility matrix

1. Edit `px4_doctor/data/compatibility.yaml` directly
2. Follow the existing YAML schema (`schema_version` stays the same for patch changes)
3. Submit a PR with a note on what changed and a link to the relevant release announcement

## Reporting a false positive or false negative

Open a GitHub issue with:
- Output of: `px4-doctor --json`
- Output of: `px4-doctor --version`
- Your OS, ROS 2 distro, Gazebo version, and PX4 version

## Running the tests

```bash
pip install pytest pytest-mock
pytest tests/ -v
```

All tests mock subprocess calls, env vars, and filesystem — no ROS 2, Gazebo, or PX4 installation required.
