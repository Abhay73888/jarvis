"""Command & action risk classification (Spec §18, §26, §34).

Terminal commands are classified CRITICAL > HIGH > MEDIUM > LOW by pattern.
Unknown commands default to MEDIUM (never silently assume a command is safe).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


class RiskLevel(int, Enum):
    LOW = 0
    MEDIUM = 1
    HIGH = 2
    CRITICAL = 3

    @property
    def label(self) -> str:
        return self.name


@dataclass(frozen=True)
class RiskAssessment:
    level: RiskLevel
    reasons: tuple[str, ...]

    @property
    def requires_confirmation(self) -> bool:
        return self.level >= RiskLevel.MEDIUM


# Ordered: first match wins, so earlier tiers are the dangerous ones.
_CRITICAL: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bdiskpart\b", re.I), "disk partitioning tool"),
    (re.compile(r"\bvssadmin\b", re.I), "volume shadow copy manipulation"),
    (re.compile(r"\bbcdedit\b", re.I), "boot configuration modification"),
    (re.compile(r"\bcipher\s+/w", re.I), "drive overwrite/wipe"),
    (re.compile(r"\bformat(\.com|\.exe)?\b\s+[a-z]:", re.I), "disk format"),
    (re.compile(r"\bmkfs(\.\w+)?\b", re.I), "filesystem creation"),
    (re.compile(r"\bdd\s+if=", re.I), "raw disk write"),
    (re.compile(r"(invoke-expression|\biex\b)\b", re.I), "arbitrary script execution"),
    (re.compile(r"\b(irm|invoke-webrequest|iwr|curl|wget)[^|]*\|\s*(iex|invoke-expression|sh|bash|powershell)", re.I), "download-and-execute pipeline"),
    (re.compile(r"\breg(edit)?\s+(add|delete|import|restore)\b.*hk(lm|ey_local_machine)", re.I), "machine registry modification"),
    (re.compile(r"\bnetsh\s+(advfirewall|firewall)", re.I), "firewall reconfiguration"),
    (re.compile(r"\bset-executionpolicy\b", re.I), "PowerShell execution policy change"),
    (re.compile(r"\bshutdown\b|\brestart\s+/s\b|\bstop-computer\b|\brestart-computer\b", re.I), "system shutdown/restart"),
    (re.compile(r"(rm\s+-rf|sudo\s+rm\s+-rf)\s+(/|~|\$home|c:\\)", re.I), "recursive delete of a root/home path"),
    (re.compile(r"\brd\s+/s|\brmdir\s+/s\b", re.I), "recursive directory deletion (Windows)"),
)

_HIGH: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"(sudo\s+)?rm\s+(-\w+\s+)*-r\w*f", re.I), "recursive force deletion"),
    (re.compile(r"\bremove-item\b.*-recurse", re.I), "recursive deletion"),
    (re.compile(r"\bdel\s+/[sf]", re.I), "forced/recursive file deletion"),
    (re.compile(r"\breg\s+(add|delete|import)\b", re.I), "registry modification"),
    (re.compile(r"\bregedit\b|\breg\b\s+import", re.I), "registry editor"),
    (re.compile(r"\btaskkill\b.*(/f|/im)", re.I), "forced process termination"),
    (re.compile(r"\bkill\s+-9|\bpkill\b|\btaskkill\b", re.I), "process termination"),
    (re.compile(r"\bschtasks\s+/create|\bcron\b|\bcrontab\b", re.I), "scheduled task creation"),
    (re.compile(r"\bsc\s+(config|delete)\b", re.I), "service reconfiguration"),
    (re.compile(r"\btakeown\b|\bicacls\b", re.I), "ownership/ACL modification"),
    (re.compile(r"\bnet\s+user\b", re.I), "user account modification"),
    (re.compile(r"\bgit\s+(reset\s+--hard|clean\s+-[fx]d|push\s+--force|push\s+-f)", re.I), "destructive git operation"),
    (re.compile(r"\bdocker\s+(rm|rmi|system\s+prune|volume\s+rm)", re.I), "docker object removal"),
    (re.compile(r"\btruncate\b|\bshred\b", re.I), "file destruction"),
)

_MEDIUM: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\b(pip3?|python\s+-m\s+pip)\s+(install|uninstall)", re.I), "Python package change"),
    (re.compile(r"\bnpm\s+(install|i|uninstall|ci|update)\b|\byarn\s+(add|install|remove)", re.I), "Node package change"),
    (re.compile(r"\b(winget|choco|scoop|apt(-get)?|brew|dnf|pacman)\s+install", re.I), "system package installation"),
    (re.compile(r"\bgit\s+(pull|push|commit|merge|rebase|checkout|stash|restore)", re.I), "git state change"),
    (re.compile(r"\bnpx\s+\S+|\bcargo\s+install|\bgo\s+install|\bdotnet\s+tool", re.I), "remote tool execution/install"),
    (re.compile(r"\bdocker\s+(run|exec|build|compose)", re.I), "container execution"),
    (re.compile(r"\bnew-item\b|\bmkdir\b|\btouch\b", re.I), "filesystem mutation"),
    (re.compile(r"\bmove-item\b|\bmove\b|\bmv\b|\bcopy-item\b|\bcp\b", re.I), "file move/copy"),
    (re.compile(r"\bcurl\b|\bwget\b|\binvoke-webrequest\b|\birm\b", re.I), "network download"),
)

_LOW_HINTS = re.compile(
    r"(?i)^(\s*(dir|ls|pwd|cd|cat|type|echo|whoami|hostname|date|time|clear|cls|tree|find|findstr|where|which)"
    r"(\.exe)?\b.*|.*(git\s+(status|log|diff|branch|show)|--version|-v|python\s+--version|node\s+--version)$)"
)


def classify_command(command: str) -> RiskAssessment:
    """Classify a shell command string. Unknown commands → MEDIUM by default."""
    command = command.strip()
    for pattern, reason in _CRITICAL:
        if pattern.search(command):
            return RiskAssessment(RiskLevel.CRITICAL, (reason,))
    for pattern, reason in _HIGH:
        if pattern.search(command):
            return RiskAssessment(RiskLevel.HIGH, (reason,))
    for pattern, reason in _MEDIUM:
        if pattern.search(command):
            return RiskAssessment(RiskLevel.MEDIUM, (reason,))
    if _LOW_HINTS.match(command):
        return RiskAssessment(RiskLevel.LOW, ("read-only command",))
    return RiskAssessment(RiskLevel.MEDIUM, ("unrecognized command — defaulting to caution",))
