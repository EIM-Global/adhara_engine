"""
Abstract base class for scan drivers.

Scan drivers are responsible for static analysis of source code before
the build stage. They are decoupled from building — a scan driver doesn't
know how or where the image will be built.

The pipeline orchestrator calls:
  driver.scan(request) -> ScanResult
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Callable


@dataclass
class ScanFinding:
    """A single finding from a scan."""

    rule_id: str
    severity: str  # "critical", "high", "medium", "low", "info"
    message: str
    file: str | None = None
    line: int | None = None
    column: int | None = None
    category: str | None = None  # "security", "correctness", "performance"
    cwe: str | None = None  # CWE-79, etc.
    owasp: str | None = None  # A1, etc.


@dataclass
class ScanRequest:
    """Input to a scan driver."""

    site_id: str
    site_slug: str
    source_dir: str  # Path to cloned source code

    # Configuration
    fail_on: str = "critical"  # severity threshold: "critical", "high", "medium", "low"
    config_file: str | None = None  # scanner-specific config path
    exclude_patterns: list[str] = field(default_factory=list)
    include_patterns: list[str] = field(default_factory=list)

    # Scanner-specific options
    extra_args: dict[str, str] = field(default_factory=dict)

    # Logging callback
    log_callback: Callable[[str, str], None] | None = None


@dataclass
class ScanResult:
    """Output from a scan driver."""

    success: bool  # Did the scan run without errors?
    passed: bool | None = None  # Did it pass the threshold? None = not scanned
    error: str | None = None

    # Findings
    findings: list[ScanFinding] = field(default_factory=list)
    findings_by_severity: dict[str, int] = field(default_factory=dict)
    total_findings: int = 0

    # Logs
    logs: str = ""
    duration_ms: int | None = None

    # Raw scanner output (for metadata storage)
    raw_output: dict | None = None


# Severity ordering for threshold comparison
SEVERITY_ORDER = {
    "info": 0,
    "low": 1,
    "medium": 2,
    "high": 3,
    "critical": 4,
}


def findings_exceed_threshold(
    findings: list[ScanFinding], threshold: str
) -> bool:
    """Check if any findings meet or exceed the severity threshold."""
    threshold_level = SEVERITY_ORDER.get(threshold.lower(), 4)
    return any(
        SEVERITY_ORDER.get(f.severity.lower(), 0) >= threshold_level
        for f in findings
    )


class ScanDriver(ABC):
    """Abstract interface for code scan drivers.

    Each driver implements the scan method, which analyzes source code
    and returns structured findings.
    """

    @abstractmethod
    async def scan(self, request: ScanRequest) -> ScanResult:
        """Run static analysis on source code.

        Args:
            request: Scan configuration and source location

        Returns:
            ScanResult with findings and pass/fail status
        """
        ...

    @abstractmethod
    async def health(self) -> bool:
        """Check if the scanner is available and functional."""
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable scanner name."""
        ...
