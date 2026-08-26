"""Self-Healing and Error Classification Engine (Spec §19).

When a command or tool action fails:
1. Classifies error category (missing dependency, permission denied, network error, path not found).
2. Formulates safe remediation proposals (e.g. `pip install <package>`, directory creation, retry).
3. Applies safe retries up to max 2 attempts with honest status reporting.
"""
from __future__ import annotations

from enum import Enum
import re
from typing import Optional

from app.core.logging import get_logger

log = get_logger("brain.self_heal")


class ErrorCategory(str, Enum):
    MISSING_DEPENDENCY = "missing_dependency"
    PERMISSION_DENIED = "permission_denied"
    NETWORK_TIMEOUT = "network_timeout"
    PATH_NOT_FOUND = "path_not_found"
    SYNTAX_ERROR = "syntax_error"
    COMMAND_NOT_FOUND = "command_not_found"
    UNKNOWN = "unknown"


class ErrorClassifier:
    """Classifies execution errors and determines safe healing actions."""

    @staticmethod
    def classify(error_text: str) -> tuple[ErrorCategory, Optional[str]]:
        """Classify error string and extract key detail (e.g. missing package name)."""
        if not error_text:
            return ErrorCategory.UNKNOWN, None

        # 1. Missing python module
        m_mod = re.search(r"ModuleNotFoundError:\s+No module named ['\"]?([a-zA-Z0-9_-]+)['\"]?", error_text)
        if m_mod:
            return ErrorCategory.MISSING_DEPENDENCY, m_mod.group(1)

        # 2. Command not found
        m_cmd = re.search(r"(?:is not recognized as an internal or external command|command not found:\s*([a-zA-Z0-9_-]+))", error_text, re.I)
        if m_cmd:
            cmd = m_cmd.group(1) if m_cmd.lastindex else None
            return ErrorCategory.COMMAND_NOT_FOUND, cmd

        # 3. Permission denied
        if re.search(r"(?:PermissionError|Access is denied|Permission denied|EACCES)", error_text, re.I):
            return ErrorCategory.PERMISSION_DENIED, None

        # 4. File / Path not found
        if re.search(r"(?:FileNotFoundError|No such file or directory|The system cannot find the path specified)", error_text, re.I):
            return ErrorCategory.PATH_NOT_FOUND, None

        # 5. Network / Timeout
        if re.search(r"(?:ConnectionRefusedError|TimeoutError|timed out|Failed to establish a new connection|getaddrinfo failed)", error_text, re.I):
            return ErrorCategory.NETWORK_TIMEOUT, None

        # 6. Syntax error
        if re.search(r"(?:SyntaxError|IndentationError|Invalid syntax)", error_text, re.I):
            return ErrorCategory.SYNTAX_ERROR, None

        return ErrorCategory.UNKNOWN, None

    @staticmethod
    def propose_fix(category: ErrorCategory, detail: Optional[str] = None) -> Optional[dict]:
        """Propose a concrete, safe action to heal the error."""
        if category == ErrorCategory.MISSING_DEPENDENCY and detail:
            return {
                "action": "install_package",
                "package": detail,
                "command": f"pip install {detail}",
                "description": f"Install missing Python dependency '{detail}' using pip.",
                "safe_to_auto_propose": True,
            }

        if category == ErrorCategory.PATH_NOT_FOUND:
            return {
                "action": "verify_path",
                "description": "Check if the target directory exists or search for the file location.",
                "safe_to_auto_propose": True,
            }

        if category == ErrorCategory.NETWORK_TIMEOUT:
            return {
                "action": "retry",
                "description": "Retry request after a brief delay.",
                "safe_to_auto_propose": True,
            }

        return None
