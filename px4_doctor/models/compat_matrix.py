"""Compatibility matrix — loads and queries compatibility.yaml."""

from __future__ import annotations

import importlib.resources
from pathlib import Path
from typing import Any


_GITHUB_URL = (
    "https://raw.githubusercontent.com/carloangulo/px4-sitl-doctor"
    "/main/px4_doctor/data/compatibility.yaml"
)
_FETCH_TIMEOUT = 2  # seconds


def _load_bundled() -> dict:
    """Load the YAML bundled with the package."""
    import yaml  # type: ignore[import-untyped]

    try:
        # Python 3.9+ importlib.resources API
        ref = importlib.resources.files("px4_doctor") / "data" / "compatibility.yaml"
        with importlib.resources.as_file(ref) as p:
            return yaml.safe_load(p.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        # Fallback: find relative to this file
        data_path = Path(__file__).parent.parent / "data" / "compatibility.yaml"
        import yaml
        return yaml.safe_load(data_path.read_text(encoding="utf-8"))


def _fetch_remote() -> dict | None:
    """Attempt to fetch the latest YAML from GitHub. Returns None on any error."""
    try:
        import requests  # type: ignore[import-untyped]
        import yaml  # type: ignore[import-untyped]

        resp = requests.get(_GITHUB_URL, timeout=_FETCH_TIMEOUT)
        resp.raise_for_status()
        return yaml.safe_load(resp.text)
    except Exception:  # noqa: BLE001
        return None


class CompatMatrix:
    """Wrapper around the compatibility YAML data.

    On first instantiation it attempts to fetch the latest rules from GitHub
    (2-second timeout). On failure it silently falls back to the bundled copy.
    """

    def __init__(self, offline: bool = False) -> None:
        data: dict | None = None
        if not offline:
            data = _fetch_remote()
        if data is None:
            data = _load_bundled()
        self._data: dict[str, Any] = data

    # ------------------------------------------------------------------ #
    # Public query methods                                                 #
    # ------------------------------------------------------------------ #

    def get_combos(self) -> list[dict]:
        """Return all known compatible version combinations."""
        return self._data.get("combos", [])

    def get_platforms(self) -> list[dict]:
        """Return all platform descriptors."""
        return self._data.get("platforms", [])

    def get_platform_ids(self) -> list[str]:
        return [p["id"] for p in self.get_platforms()]

    def is_ros2_gazebo_compatible(self, ros2_distro: str, gazebo_name: str) -> bool:
        """Return True if *ros2_distro* + *gazebo_name* appear together in any combo."""
        ros2_distro = ros2_distro.lower().strip()
        gazebo_name = gazebo_name.lower().strip()
        for combo in self.get_combos():
            if (
                combo.get("ros2", "").lower() == ros2_distro
                and combo.get("gazebo", "").lower() == gazebo_name
            ):
                return True
        return False

    def get_combo_for(self, ros2_distro: str, gazebo_name: str) -> dict | None:
        """Return the first matching combo dict, or None."""
        ros2_distro = ros2_distro.lower().strip()
        gazebo_name = gazebo_name.lower().strip()
        for combo in self.get_combos():
            if (
                combo.get("ros2", "").lower() == ros2_distro
                and combo.get("gazebo", "").lower() == gazebo_name
            ):
                return combo
        return None

    def get_required_env_vars(self, platform: str) -> list[dict]:
        """Return required env vars for *platform*.

        Falls back to "linux" entries for "ubuntu_*" and "windows_wsl2" variants.
        """
        env_section: dict = self._data.get("required_env_vars", {})

        # Map platform IDs to YAML keys
        if platform in ("ubuntu_22_04", "ubuntu_24_04", "ubuntu_other"):
            key = "linux"
        elif platform == "windows_wsl2":
            linux_vars = env_section.get("linux", [])
            wsl_vars = env_section.get("windows_wsl2", [])
            return linux_vars + wsl_vars
        else:
            key = platform

        return env_section.get(key, [])

    def get_required_binaries(self, platform: str) -> list[dict]:
        """Return required binaries for *platform*."""
        bin_section: dict = self._data.get("required_binaries", {})
        if platform in ("ubuntu_22_04", "ubuntu_24_04", "ubuntu_other", "windows_wsl2"):
            key = "linux" if platform != "windows_wsl2" else "windows_wsl2"
            return bin_section.get(key, bin_section.get("linux", []))
        return []

    def get_required_libraries(self, platform: str) -> list[dict]:
        """Return required shared libraries for *platform*."""
        lib_section: dict = self._data.get("required_libraries", {})
        if platform in ("ubuntu_22_04", "ubuntu_24_04", "ubuntu_other", "windows_wsl2"):
            return lib_section.get("linux", [])
        return []

    def get_required_ports(self) -> list[dict]:
        """Return the list of required port descriptors (platform-agnostic)."""
        return self._data.get("required_ports", [])

    def get_fix(self, binary_name: str, platform: str) -> str | None:
        """Return the fix command for a missing binary, or None."""
        for entry in self.get_required_binaries(platform):
            if entry.get("name") == binary_name:
                return entry.get("fix")
        return None
