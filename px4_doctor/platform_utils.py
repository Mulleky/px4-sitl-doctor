"""Cross-platform utilities used by all checkers."""

from __future__ import annotations

import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path

from packaging.version import InvalidVersion, Version


def detect_platform() -> str:
    """Return a canonical platform string.

    Possible return values:
      "ubuntu_22_04", "ubuntu_24_04", "ubuntu_other",
      "windows_wsl2", "windows_native", "macos", "unknown"
    """
    system = platform.system()

    if system == "Linux":
        # Check if we are inside WSL2
        proc_version = Path("/proc/version")
        if proc_version.exists():
            try:
                content = proc_version.read_text(encoding="utf-8", errors="replace")
                if "microsoft" in content.lower() or "wsl" in content.lower():
                    return "windows_wsl2"
            except OSError:
                pass

        # Read /etc/os-release for Ubuntu version
        os_release = Path("/etc/os-release")
        if os_release.exists():
            try:
                data = {}
                for line in os_release.read_text(encoding="utf-8").splitlines():
                    if "=" in line:
                        k, _, v = line.partition("=")
                        data[k.strip()] = v.strip().strip('"')
                distro_id = data.get("ID", "").lower()
                version_id = data.get("VERSION_ID", "")
                if distro_id == "ubuntu":
                    if version_id == "22.04":
                        return "ubuntu_22_04"
                    if version_id == "24.04":
                        return "ubuntu_24_04"
                    return "ubuntu_other"
            except OSError:
                pass
        return "unknown"

    if system == "Windows":
        return "windows_native"

    if system == "Darwin":
        return "macos"

    return "unknown"


def run_cmd(
    args: list[str],
    timeout: int = 5,
) -> tuple[int, str, str]:
    """Run a subprocess and return (returncode, stdout, stderr).

    Never raises. Returns (-1, "", error_message) on any exception.
    """
    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result.returncode, result.stdout, result.stderr
    except FileNotFoundError:
        return -1, "", f"Binary not found: {args[0]}"
    except subprocess.TimeoutExpired:
        return -1, "", f"Command timed out after {timeout}s: {' '.join(args)}"
    except Exception as exc:  # noqa: BLE001
        return -1, "", str(exc)


def find_binary(name: str) -> str | None:
    """Return the full path to *name* if it is on PATH, else None."""
    return shutil.which(name)


def parse_version(raw: str) -> Version | None:
    """Parse a version string using packaging, stripping common prefixes.

    Returns a packaging.version.Version, or None if unparseable.
    """
    if not raw:
        return None

    raw = raw.strip()
    # Strip common CLI output prefixes: "v1.2.3", "gz version 8.6.0", etc.
    raw = re.sub(r"^[^\d]*", "", raw)
    tokens = raw.split()
    raw = tokens[0] if tokens else ""
    if not raw:
        return None
    try:
        return Version(raw)
    except InvalidVersion:
        m = re.match(r"(\d+(?:\.\d+)*)", raw)
        if m:
            try:
                return Version(m.group(1))
            except InvalidVersion:
                pass
    return None


def get_home() -> Path:
    """Return the home directory.

    On WSL2, this is the Linux home, not the Windows user directory.
    """
    # Path.home() correctly returns /home/<user> inside WSL2.
    return Path.home()
