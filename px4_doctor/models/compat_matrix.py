"""Compatibility matrix — loads and queries compatibility.yaml."""

from __future__ import annotations

import importlib.resources
import logging
import os
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)


_GITHUB_URL = (
    "https://raw.githubusercontent.com/Mulleky/px4-sitl-doctor"
    "/main/px4_doctor/data/compatibility.yaml"
)
_FETCH_TIMEOUT = 2  # seconds


def user_override_path() -> Path:
    """Location of the user-writable matrix override (populated by --update-matrix)."""
    xdg = os.environ.get("XDG_DATA_HOME")
    base = Path(xdg) if xdg else Path.home() / ".local" / "share"
    return base / "px4-doctor" / "compatibility.yaml"


def _load_user_override() -> dict | None:
    """Return parsed YAML from the user-override path, or None if not present/invalid."""
    path = user_override_path()
    if not path.exists():
        return None
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        logger.debug("Failed to load user-override matrix at %s: %s", path, exc)
        return None


def _load_bundled() -> dict:
    """Load the YAML bundled with the package.

    Raises FileNotFoundError or yaml.YAMLError if the bundled file is missing or
    malformed — this is a packaging bug, not a runtime condition to hide.
    """
    try:
        ref = importlib.resources.files("px4_doctor") / "data" / "compatibility.yaml"
        with importlib.resources.as_file(ref) as p:
            return yaml.safe_load(p.read_text(encoding="utf-8"))
    except (FileNotFoundError, ModuleNotFoundError) as exc:
        logger.debug("importlib.resources lookup failed, using relative path: %s", exc)
        data_path = Path(__file__).parent.parent / "data" / "compatibility.yaml"
        return yaml.safe_load(data_path.read_text(encoding="utf-8"))


def _fetch_remote() -> dict | None:
    """Attempt to fetch the latest YAML from GitHub. Returns None on failure."""
    try:
        import requests  # type: ignore[import-untyped]
    except ImportError:
        logger.debug("requests not installed; skipping remote matrix fetch")
        return None

    try:
        resp = requests.get(_GITHUB_URL, timeout=_FETCH_TIMEOUT)
        resp.raise_for_status()
        return yaml.safe_load(resp.text)
    except (requests.RequestException, yaml.YAMLError) as exc:
        logger.debug("Remote matrix fetch failed: %s", exc)
        return None


class CompatMatrix:
    """Wrapper around the compatibility YAML data.

    Load priority (highest → lowest):
      1. Remote GitHub fetch (only if ``fetch_remote=True``)
      2. User-override path (``~/.local/share/px4-doctor/compatibility.yaml``)
      3. Bundled YAML shipped with the package

    The default never touches the network, so CLI startup is fast and offline-safe.
    Pass ``fetch_remote=True`` only when the caller specifically wants freshness.
    """

    def __init__(self, fetch_remote: bool = False, offline: bool | None = None) -> None:
        # ``offline`` is kept for backward compatibility and is ignored —
        # remote fetch is now opt-in via ``fetch_remote``.
        del offline
        data: dict | None = None
        if fetch_remote:
            data = _fetch_remote()
        if data is None:
            data = _load_user_override()
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
            key = "windows_wsl2" if platform == "windows_wsl2" else "linux"
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
