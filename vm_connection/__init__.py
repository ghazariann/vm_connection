"""VM Connection package for SSH connectivity."""

from .connection import SSHConnection
from .exceptions import (
    SSHConnectionError,
    KeyFileNotFoundError,
    AuthenticationFailedError,
    UnexpectedRebootError,
    OverallTimeoutError,
    HostUnreachableError,
    UnexpectedError,
    CommandExecutionFailedError,
    LostConnectionDuringExecutionError
)

__all__ = [
    "SSHConnection",
    "SSHConnectionError", 
    "KeyFileNotFoundError",
    "AuthenticationFailedError", 
    "UnexpectedRebootError",
    "OverallTimeoutError",
    "HostUnreachableError",
    "UnexpectedError",
    "CommandExecutionFailedError",
    "LostConnectionDuringExecutionError"
]
__version__ = "0.1.0"