"""Abstract base class that every checker must subclass."""

from __future__ import annotations

from abc import ABC, abstractmethod

from px4_doctor.models.result import CheckResult


class BaseChecker(ABC):
    """Base class for all environment checkers.

    Subclass this and implement :meth:`run`.  Each checker is self-contained
    and must not depend on any other checker's results.

    Class-level attributes to set in each subclass:

    .. code-block:: python

        name      = "Human-readable check name shown in the report"
        category  = "core"   # one of: core, env, network, workspace
        platforms = ["all"]  # or e.g. ["ubuntu_22_04", "ubuntu_24_04", "windows_wsl2"]
    """

    name: str = "Unnamed Checker"
    category: str = "core"
    # ["all"] means the checker runs on every detected platform.
    # Any other list means it only runs on the named platforms.
    platforms: list[str] = ["all"]

    @abstractmethod
    def run(self) -> list[CheckResult]:
        """Execute all checks in this module and return results."""

    def skip(self, reason: str) -> CheckResult:
        """Return a skip result for this checker."""
        return CheckResult(
            checker_name=self.name,
            status="skip",
            message=reason,
            fix=None,
            detail=None,
        )

    def applies_to(self, platform: str) -> bool:
        """Return True if this checker should run on *platform*."""
        if "all" in self.platforms:
            return True
        return platform in self.platforms
