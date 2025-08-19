"""Custom exceptions for vm_connection package."""


class SSHConnectionError(Exception):
    """Base exception for SSH connection errors."""
    pass


class KeyFileNotFoundError(SSHConnectionError):
    """Raised when SSH private key file doesn't exist."""
    pass


class AuthenticationFailedError(SSHConnectionError):
    """Raised when SSH authentication fails."""
    pass


class UnexpectedRebootError(SSHConnectionError):
    """Raised when a reboot is detected between two checkpoints."""
    pass


class OverallTimeoutError(SSHConnectionError):
    """Raised when command execution exceeds overall timeout."""
    pass


class HostUnreachableError(SSHConnectionError):
    """Raised when SSH host is unreachable or connection cannot be established."""
    pass


class UnexpectedError(SSHConnectionError):
    """Raised when an unexpected error occurs during SSH operations."""
    pass


class CommandExecutionFailedError(SSHConnectionError):
    """Raised when command execution fails due to streaming or execution errors."""
    pass


class LostConnectionDuringExecutionError(SSHConnectionError):
    """Raised when connection is lost during command execution."""
    pass