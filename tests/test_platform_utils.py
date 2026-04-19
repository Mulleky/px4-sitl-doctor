"""Tests for platform_utils: parse_version, run_cmd, detect_platform."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from packaging.version import Version

from px4_doctor import platform_utils
from px4_doctor.platform_utils import detect_platform, parse_version, run_cmd


class TestParseVersion:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("1.2.3", Version("1.2.3")),
            ("v1.2.3", Version("1.2.3")),
            ("V1.2.3", Version("1.2.3")),
            ("1.2", Version("1.2")),
            ("gz version 8.6.0", Version("8.6.0")),
            ("Gazebo 8.6.0-rc1", Version("8.6.0rc1")),
            ("1.2.3 and extra", Version("1.2.3")),
            ("  1.2.3  ", Version("1.2.3")),
        ],
    )
    def test_valid(self, raw, expected):
        assert parse_version(raw) == expected

    @pytest.mark.parametrize("raw", ["", "   ", "garbage", "not-a-version", "abc.def.ghi"])
    def test_invalid_returns_none(self, raw):
        assert parse_version(raw) is None

    def test_none_type_is_Version(self):
        result = parse_version("1.2.3")
        assert isinstance(result, Version)
        # Type check that .major is accessible without cast
        assert result.major == 1


class TestRunCmd:
    def test_success(self):
        # Python is a safe bet across environments
        rc, stdout, _ = run_cmd(["python", "-c", "print('hello')"])
        assert rc == 0
        assert "hello" in stdout

    def test_binary_not_found(self):
        rc, stdout, stderr = run_cmd(["this-binary-does-not-exist-xyzzy"])
        assert rc == -1
        assert stdout == ""
        assert "not found" in stderr.lower()

    def test_timeout(self, monkeypatch):
        def fake_run(*args, **kwargs):
            raise subprocess.TimeoutExpired(cmd=args[0], timeout=kwargs.get("timeout", 5))

        monkeypatch.setattr(subprocess, "run", fake_run)
        rc, stdout, stderr = run_cmd(["anything"], timeout=1)
        assert rc == -1
        assert stdout == ""
        assert "timed out" in stderr.lower()

    def test_generic_exception(self, monkeypatch):
        def fake_run(*args, **kwargs):
            raise OSError("disk full")

        monkeypatch.setattr(subprocess, "run", fake_run)
        rc, stdout, stderr = run_cmd(["anything"])
        assert rc == -1
        assert stdout == ""
        assert "disk full" in stderr


class TestDetectPlatform:
    def test_windows(self, monkeypatch):
        monkeypatch.setattr(platform_utils.platform, "system", lambda: "Windows")
        assert detect_platform() == "windows_native"

    def test_darwin(self, monkeypatch):
        monkeypatch.setattr(platform_utils.platform, "system", lambda: "Darwin")
        assert detect_platform() == "macos"

    def test_unknown(self, monkeypatch):
        monkeypatch.setattr(platform_utils.platform, "system", lambda: "FreeBSD")
        assert detect_platform() == "unknown"

    def test_linux_wsl2(self, monkeypatch, tmp_path):
        monkeypatch.setattr(platform_utils.platform, "system", lambda: "Linux")

        real_exists = Path.exists
        proc_version = tmp_path / "proc_version"
        proc_version.write_text("Linux ... Microsoft ... WSL2 ...")

        def fake_exists(self):
            if self.as_posix() == "/proc/version":
                return True
            return real_exists(self)

        def fake_read_text(self, *a, **kw):
            if self.as_posix() == "/proc/version":
                return "Linux ... Microsoft ... WSL2 ..."
            return Path.read_text(self, *a, **kw)

        monkeypatch.setattr(Path, "exists", fake_exists)
        monkeypatch.setattr(Path, "read_text", fake_read_text)
        assert detect_platform() == "windows_wsl2"

    def test_linux_ubuntu_22(self, monkeypatch):
        monkeypatch.setattr(platform_utils.platform, "system", lambda: "Linux")

        def fake_exists(self):
            return self.as_posix() == "/etc/os-release"

        def fake_read_text(self, *a, **kw):
            if self.as_posix() == "/etc/os-release":
                return 'ID=ubuntu\nVERSION_ID="22.04"\n'
            return ""

        monkeypatch.setattr(Path, "exists", fake_exists)
        monkeypatch.setattr(Path, "read_text", fake_read_text)
        assert detect_platform() == "ubuntu_22_04"

    def test_linux_ubuntu_24(self, monkeypatch):
        monkeypatch.setattr(platform_utils.platform, "system", lambda: "Linux")

        def fake_exists(self):
            return self.as_posix() == "/etc/os-release"

        def fake_read_text(self, *a, **kw):
            if self.as_posix() == "/etc/os-release":
                return 'ID=ubuntu\nVERSION_ID="24.04"\n'
            return ""

        monkeypatch.setattr(Path, "exists", fake_exists)
        monkeypatch.setattr(Path, "read_text", fake_read_text)
        assert detect_platform() == "ubuntu_24_04"

    def test_linux_ubuntu_other(self, monkeypatch):
        monkeypatch.setattr(platform_utils.platform, "system", lambda: "Linux")

        def fake_exists(self):
            return self.as_posix() == "/etc/os-release"

        def fake_read_text(self, *a, **kw):
            if self.as_posix() == "/etc/os-release":
                return 'ID=ubuntu\nVERSION_ID="20.04"\n'
            return ""

        monkeypatch.setattr(Path, "exists", fake_exists)
        monkeypatch.setattr(Path, "read_text", fake_read_text)
        assert detect_platform() == "ubuntu_other"
