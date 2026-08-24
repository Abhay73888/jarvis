"""Zero-Trust AI Sandbox & Anti-Malware Threat Interceptor (Spec §60).

Inspects commands and file actions in real-time before execution.
Hard-blocks destructive attacks, ransomware patterns, stealth download-cradles, and OS hijacking.
"""
from __future__ import annotations

import re
from typing import NamedTuple

from app.core.logging import get_logger

log = get_logger("security.sandbox")


class ThreatReport(NamedTuple):
    is_threat: bool
    threat_type: str
    reason: str
    severity: str  # LETHAL, CRITICAL, HIGH, SUSPICIOUS


# Threat signatures (Regex rules matching dangerous command behaviors)
_LETHAL_PATTERNS: list[tuple[re.Pattern, str, str]] = [
    # 1. Ransomware & Shadow Copy Deletion
    (
        re.compile(r"(?i)\b(vssadmin\s+delete\s+shadows|wmic\s+shadowcopy\s+delete|wbadmin\s+delete\s+catalog)\b"),
        "Ransomware Indicator: Volume Shadow Copy Deletion",
        "LETHAL",
    ),
    # 2. Boot configuration tampering & recovery disablement
    (
        re.compile(r"(?i)\b(bcdedit\s+(/set\s+.*(recoveryenabled\s+no|bootstatuspolicy\s+ignoreallfailures)|/delete))\b"),
        "Boot Record & Recovery Tampering",
        "LETHAL",
    ),
    # 3. System Drive / Windows root wiping
    (
        re.compile(r"(?i)(rmdir\s+/[sq]\s+[a-z]:\\windows|del\s+/[fasq]+\s+[a-z]:\\windows|\bformat\s+[a-z]:|\bdiskpart\b)"),
        "Critical OS Drive Destruction",
        "LETHAL",
    ),

    # 4. Hidden Download-and-Execute cradles
    (
        re.compile(r"(?i)\bpowershell\b.*(-enc|-encodedcommand|\biex\b|invoke-expression|downloadstring|downloadfile)"),
        "Stealth Remote Code Execution (Download Cradle)",
        "CRITICAL",
    ),

    # 5. Remote shell / reverse shell payloads
    (
        re.compile(r"(?i)\b(nc(\.exe)?\s+(-e|-c|/bin/sh|cmd\.exe)|\/dev\/tcp\/\d{1,3}\.\d{1,3}|bash\s+-i\s+>&|powershell.*net\.sockets\.tcpclient)\b"),
        "Reverse Shell / Remote Access Payload",
        "CRITICAL",
    ),
    # 6. Fork bombs and process exhaustion
    (
        re.compile(r"(:\(\)\s*\{\s*:\|:&\s*\};:|%\s*0\s*\|\s*%\s*0)"),
        "Fork Bomb / Process Exhaustion Attack",
        "CRITICAL",
    ),
    # 7. Mass Registry Run key tampering (Persistence hijacking)
    (
        re.compile(r"(?i)\b(reg\s+add\s+[\"']?(hklm|hkcu)\\software\\microsoft\\windows\\currentversion\\run\b)"),
        "Unauthorized Registry Persistence Hijacking",
        "HIGH",
    ),
    # 8. Password dumping and credential harvesting
    (
        re.compile(r"(?i)\b(mimikatz|sekurlsa|procdump.*lsass|rundll32.*comsvcs.*minidump)\b"),
        "Credential Dumping / LSASS Memory Injection",
        "LETHAL",
    ),
]


def inspect_command(command_str: str) -> ThreatReport:
    """Analyze a terminal command string for malicious signatures and lethal behaviors."""
    if not command_str or not command_str.strip():
        return ThreatReport(False, "None", "Safe empty command", "NONE")

    normalized = " ".join(command_str.split())

    for pattern, description, severity in _LETHAL_PATTERNS:
        if pattern.search(normalized):
            log.warning("MALWARE INTERCEPTED: %s [Severity: %s] -> '%s'", description, severity, command_str[:120])
            return ThreatReport(
                is_threat=True,
                threat_type=description,
                reason=f"Blocked by JARVIS Zero-Trust Sandbox: {description} (Severity: {severity})",
                severity=severity,
            )

    return ThreatReport(False, "None", "Command passed security sandbox verification", "NONE")
