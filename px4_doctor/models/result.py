"""CheckResult dataclass — the universal return type for all checkers."""

from dataclasses import dataclass, field
import dataclasses
import json


@dataclass
class CheckResult:
    checker_name: str
    status: str          # "pass" | "warn" | "fail" | "skip"
    message: str
    fix: str | None = field(default=None)
    detail: str | None = field(default=None)

    # Status semantics:
    #   pass  — requirement met, no action needed
    #   warn  — not ideal but simulation may still work
    #   fail  — will definitely cause launch failure; fix required
    #   skip  — check not applicable on this platform or config

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)
