"""UDP/TCP port availability checker."""

from __future__ import annotations

import socket

from px4_doctor.checkers.base import BaseChecker
from px4_doctor.models.result import CheckResult
from px4_doctor.platform_utils import detect_platform, run_cmd


def _get_port_owner(port: int, protocol: str) -> str | None:
    """Try to identify the process occupying *port*. Returns a description or None."""
    # Attempt psutil first (optional dependency)
    try:
        import psutil  # type: ignore[import-untyped]

        for conn in psutil.net_connections(kind="udp" if protocol == "UDP" else "tcp"):
            if conn.laddr.port == port:
                try:
                    proc = psutil.Process(conn.pid)
                    return f"PID {conn.pid} ({proc.name()})"
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    return f"PID {conn.pid}"
        return None
    except ImportError:
        pass

    # Fallback: lsof (Linux)
    proto_flag = "UDP" if protocol == "UDP" else "TCP"
    rc, stdout, _ = run_cmd(["lsof", "-i", f"{proto_flag}:{port}", "-t"], timeout=3)
    if rc == 0 and stdout.strip():
        pids = stdout.strip().splitlines()
        return f"PID(s) {', '.join(pids)} (install psutil for process names)"

    return None


def _check_port(port: int, protocol: str) -> bool:
    """Return True if the port is available (bind succeeds)."""
    family = socket.AF_INET
    sock_type = socket.SOCK_DGRAM if protocol == "UDP" else socket.SOCK_STREAM
    sock = socket.socket(family, sock_type)
    try:
        sock.bind(("0.0.0.0", port))
        return True
    except OSError:
        return False
    finally:
        sock.close()


class PortChecker(BaseChecker):
    name = "Port Availability"
    category = "network"
    platforms = ["all"]

    def __init__(self, matrix=None) -> None:
        self._matrix = matrix
        self._platform = detect_platform()

    def run(self) -> list[CheckResult]:
        results: list[CheckResult] = []

        if not self._matrix:
            return [self.skip("No compatibility matrix — skipping port checks.")]

        ports = self._matrix.get_required_ports()
        if not ports:
            return [self.skip("No required ports defined in compatibility matrix.")]

        for port_def in ports:
            port = port_def.get("port", 0)
            protocol = port_def.get("protocol", "UDP").upper()
            description = port_def.get("description", "")

            if _check_port(port, protocol):
                results.append(CheckResult(
                    checker_name=f"Port {port}/{protocol}",
                    status="pass",
                    message=f"{protocol} port {port} is available — {description}",
                ))
            else:
                owner = _get_port_owner(port, protocol)
                owner_str = f" (occupied by: {owner})" if owner else ""
                results.append(CheckResult(
                    checker_name=f"Port {port}/{protocol}",
                    status="fail",
                    message=f"{protocol} port {port} is already in use{owner_str} — {description}",
                    fix=(
                        f"Find and stop the process using the port:\n"
                        f"  sudo lsof -i {protocol}:{port}\n"
                        f"  kill $(lsof -t -i {protocol}:{port})"
                    ),
                    detail=(
                        "Install psutil (`pip install psutil`) for automatic process identification."
                        if not owner else None
                    ),
                ))

        return results
