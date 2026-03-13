"""
Scan drivers for Adhara Engine.

A scan driver handles the SCAN phase of the pipeline — running static
analysis on source code before building. Decoupled from build drivers.

Available scanners:
  - semgrep: Semgrep open-source scanner (30+ languages)
  - (future) fortify: Fortify static analysis
"""

from app.services.scan_drivers.base import (
    ScanDriver,
    ScanFinding,
    ScanRequest,
    ScanResult,
    findings_exceed_threshold,
)
from app.services.scan_drivers.semgrep import SemgrepScanner

# Registry of available scan drivers
SCANNERS: dict[str, type[ScanDriver]] = {
    "semgrep": SemgrepScanner,
}

DEFAULT_SCANNER = "semgrep"


def get_scan_driver(scanner_name: str | None = None) -> ScanDriver:
    """Get a scan driver instance by name. Falls back to DEFAULT_SCANNER."""
    name = scanner_name or DEFAULT_SCANNER
    cls = SCANNERS.get(name)
    if cls is None:
        raise ValueError(
            f"Unknown scan driver: {name}. Available: {list(SCANNERS.keys())}"
        )
    return cls()


__all__ = [
    "ScanDriver",
    "ScanRequest",
    "ScanResult",
    "ScanFinding",
    "SemgrepScanner",
    "get_scan_driver",
    "findings_exceed_threshold",
    "SCANNERS",
    "DEFAULT_SCANNER",
]
