"""Exception hierarchy. User-facing messages stay clean; details go to logs.

Spec §42: never show raw stack traces to normal users — `friendly` carries the
user-facing message, dev mode surfaces `detail`.
"""
from __future__ import annotations


class JarvisError(Exception):
    """Base class for all JARVIS errors."""

    friendly: str = "Something went wrong while handling that."

    def __init__(self, friendly: str | None = None, detail: str | None = None) -> None:
        self.friendly = friendly or self.friendly
        self.detail = detail or self.friendly
        super().__init__(self.detail)


class ConfigError(JarvisError):
    friendly = "There is a problem with the configuration files."


class ValidationError(JarvisError):
    friendly = "That request had invalid parameters."


class ToolError(JarvisError):
    friendly = "That action could not be completed."


class ToolValidationError(ValidationError):
    friendly = "The parameters for that action were invalid."


class PermissionDeniedError(JarvisError):
    friendly = "That action is not permitted by your permission settings."


class ProviderError(JarvisError):
    friendly = "I could not reach the AI provider. Check your API key and connection."

    def __init__(self, friendly: str | None = None, detail: str | None = None,
                 status_code: int | None = None) -> None:
        self.status_code = status_code
        super().__init__(friendly, detail)


class MemoryError_(JarvisError):
    friendly = "There was a problem accessing memory."


class CancelledError_(JarvisError):
    friendly = "Task cancelled."
