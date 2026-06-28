# src/contracts/versioning.py
# Contract version management.

from dataclasses import dataclass
from typing import Optional

CURRENT_CONTRACT_VERSION = "qapp-v1.0"
CURRENT_ENGINE_VERSION   = "2.0"
CURRENT_RUNTIME_VERSION  = "1.0.0"


@dataclass(frozen=True)
class ContractVersion:
    major: int
    minor: int
    patch: int
    label: str = ""

    @staticmethod
    def parse(version_str: str) -> "ContractVersion":
        try:
            clean = version_str.lstrip("v").lstrip("qapp-v")
            parts = clean.split(".")
            major = int(parts[0]) if len(parts) > 0 else 0
            minor = int(parts[1]) if len(parts) > 1 else 0
            patch = int(parts[2]) if len(parts) > 2 else 0
            return ContractVersion(major=major, minor=minor, patch=patch, label=version_str)
        except Exception:
            return ContractVersion(major=0, minor=0, patch=0, label=version_str)

    def is_compatible_with(self, other: "ContractVersion") -> bool:
        return self.major == other.major

    def __str__(self) -> str:
        return self.label or f"{self.major}.{self.minor}.{self.patch}"


def check_version_compatibility(producer_version: str, consumer_version: str) -> dict:
    p = ContractVersion.parse(producer_version)
    c = ContractVersion.parse(consumer_version)
    compatible = p.is_compatible_with(c)
    return {
        "compatible":        compatible,
        "producer_version":  producer_version,
        "consumer_version":  consumer_version,
        "reason":            "Major versions match" if compatible else
                             f"Major version mismatch: {p.major} vs {c.major}",
    }


def get_version_manifest() -> dict:
    return {
        "contract_version": CURRENT_CONTRACT_VERSION,
        "engine_version":   CURRENT_ENGINE_VERSION,
        "runtime_version":  CURRENT_RUNTIME_VERSION,
        "schema":           "engine_event_v2.0",
    }
