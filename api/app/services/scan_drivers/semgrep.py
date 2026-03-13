"""
Semgrep scan driver — runs Semgrep static analysis on source code.

Semgrep is an open-source static analysis tool that supports 30+ languages.
It uses pattern matching and taint analysis to find security vulnerabilities,
bugs, and code quality issues.

Usage:
  - Requires `semgrep` to be installed in the worker container
  - Uses `--config=auto` by default (Semgrep's recommended ruleset)
  - Custom config can be specified via ScanRequest.config_file
"""

import asyncio
import json
import logging
import time

from app.services.scan_drivers.base import (
    ScanDriver,
    ScanFinding,
    ScanRequest,
    ScanResult,
    findings_exceed_threshold,
)

logger = logging.getLogger(__name__)


class SemgrepScanner(ScanDriver):
    """Runs Semgrep for static analysis."""

    @property
    def name(self) -> str:
        return "Semgrep"

    def _log(self, request: ScanRequest, line: str):
        if request.log_callback:
            request.log_callback("scan", line)

    async def scan(self, request: ScanRequest) -> ScanResult:
        start = time.monotonic()
        logs = []

        try:
            msg = f"Running Semgrep scan (fail on: {request.fail_on})..."
            logs.append(msg)
            self._log(request, msg)

            # Build command
            cmd = ["semgrep", "scan"]

            # Config
            if request.config_file:
                cmd.extend(["--config", request.config_file])
            else:
                cmd.extend(["--config=auto"])

            # JSON output for structured parsing
            cmd.append("--json")

            # Exclude patterns
            for pattern in request.exclude_patterns:
                cmd.extend(["--exclude", pattern])

            # Include patterns
            for pattern in request.include_patterns:
                cmd.extend(["--include", pattern])

            # Extra args
            for key, value in request.extra_args.items():
                if value:
                    cmd.extend([f"--{key}", value])
                else:
                    cmd.append(f"--{key}")

            # Target directory
            cmd.append(request.source_dir)

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()

            duration_ms = int((time.monotonic() - start) * 1000)

            # Parse JSON output
            raw_output = {}
            findings = []

            if stdout:
                try:
                    raw_output = json.loads(stdout.decode())
                except json.JSONDecodeError:
                    logs.append("Warning: Could not parse Semgrep JSON output")

            # Extract findings
            for result in raw_output.get("results", []):
                severity = result.get("extra", {}).get("severity", "info").lower()
                finding = ScanFinding(
                    rule_id=result.get("check_id", "unknown"),
                    severity=severity,
                    message=result.get("extra", {}).get("message", ""),
                    file=result.get("path"),
                    line=result.get("start", {}).get("line"),
                    column=result.get("start", {}).get("col"),
                    category=result.get("extra", {}).get("metadata", {}).get("category"),
                    cwe=_extract_cwe(result),
                    owasp=_extract_owasp(result),
                )
                findings.append(finding)

            # Count by severity
            by_severity: dict[str, int] = {}
            for f in findings:
                by_severity[f.severity] = by_severity.get(f.severity, 0) + 1

            # Determine pass/fail
            passed = not findings_exceed_threshold(findings, request.fail_on)

            # Summary
            summary_parts = []
            for sev in ["critical", "high", "medium", "low", "info"]:
                count = by_severity.get(sev, 0)
                if count > 0:
                    summary_parts.append(f"{count} {sev}")

            if summary_parts:
                summary = f"Found: {', '.join(summary_parts)}"
            else:
                summary = "No findings"

            if passed:
                msg = f"Scan PASSED. {summary}"
            else:
                msg = f"Scan FAILED. {summary} (threshold: {request.fail_on})"
            logs.append(msg)
            self._log(request, msg)

            # Include stderr warnings
            if stderr:
                stderr_text = stderr.decode().strip()
                if stderr_text:
                    logs.append(f"Semgrep stderr: {stderr_text[:500]}")

            return ScanResult(
                success=True,
                passed=passed,
                findings=findings,
                findings_by_severity=by_severity,
                total_findings=len(findings),
                logs="\n".join(logs),
                duration_ms=duration_ms,
                raw_output=raw_output,
            )

        except FileNotFoundError:
            duration_ms = int((time.monotonic() - start) * 1000)
            msg = "Semgrep not installed — scan skipped"
            logs.append(msg)
            self._log(request, msg)
            return ScanResult(
                success=True,
                passed=None,
                logs="\n".join(logs),
                duration_ms=duration_ms,
            )

        except Exception as e:
            duration_ms = int((time.monotonic() - start) * 1000)
            return ScanResult(
                success=False,
                error=f"Scan error: {e}",
                logs="\n".join(logs),
                duration_ms=duration_ms,
            )

    async def health(self) -> bool:
        """Check if semgrep is available."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "semgrep", "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate()
            return proc.returncode == 0
        except FileNotFoundError:
            return False


def _extract_cwe(result: dict) -> str | None:
    """Extract CWE ID from Semgrep result metadata."""
    metadata = result.get("extra", {}).get("metadata", {})
    cwe = metadata.get("cwe")
    if isinstance(cwe, list) and cwe:
        return cwe[0]
    if isinstance(cwe, str):
        return cwe
    return None


def _extract_owasp(result: dict) -> str | None:
    """Extract OWASP category from Semgrep result metadata."""
    metadata = result.get("extra", {}).get("metadata", {})
    owasp = metadata.get("owasp")
    if isinstance(owasp, list) and owasp:
        return owasp[0]
    if isinstance(owasp, str):
        return owasp
    return None
