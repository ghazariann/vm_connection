"""SSH Connection module for connecting to remote Linux VMs."""

import logging
from pathlib import Path
from typing import Optional, Tuple

import paramiko
from paramiko.ssh_exception import (
    AuthenticationException,
    NoValidConnectionsError,
    SSHException,
)

logger = logging.getLogger(__name__)


class SSHConnectionError(Exception):
    """Custom exception for SSH connection errors."""
    pass


class SSHConnection:
    """Handles SSH connections to remote Linux VMs using paramiko.
    
    This class provides a high-level interface for SSH connections with:
    - Private key authentication
    - Command execution with output capture
    - Proper connection lifecycle management
    - Context manager support for automatic cleanup
    """
    
    def __init__(
        self, 
        host: str, 
        user: str, 
        key_path: str, 
        port: int = 22,
        timeout: int = 30
    ) -> None:
        """Initialize SSH connection parameters.
        
        Args:
            host: Remote host IP or hostname
            user: Username for SSH connection
            key_path: Path to private key file
            port: SSH port (default: 22)
            timeout: Connection timeout in seconds (default: 30)
            
        Raises:
            SSHConnectionError: If key file doesn't exist
        """
        self.host = host
        self.user = user
        self.key_path = Path(key_path)
        self.port = port
        self.timeout = timeout
        self._client: Optional[paramiko.SSHClient] = None
        
        # Validate key file exists
        if not self.key_path.exists():
            raise SSHConnectionError(f"Private key file not found: {key_path}")
    
    def connect(self) -> bool:
        """Establish SSH connection using private key authentication.
        
        Returns:
            True if connection successful, False otherwise
            
        Raises:
            SSHConnectionError: For authentication or connection failures
        """
        if self._client is not None:
            logger.warning("Already connected, disconnecting first")
            self.disconnect()
        
        try:
            logger.info(f"Connecting to {self.user}@{self.host}:{self.port}")
            
            # Create SSH client
            self._client = paramiko.SSHClient()
            
            # Auto-add host keys (in production, you'd want known_hosts verification)
            self._client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # Load private key
            try:
                private_key = paramiko.RSAKey.from_private_key_file(str(self.key_path))
            except paramiko.PasswordRequiredException:
                logger.error("Private key requires passphrase (not supported)")
                raise SSHConnectionError("Private key requires passphrase")
            except Exception as e:
                logger.error(f"Failed to load private key: {e}")
                raise SSHConnectionError(f"Invalid private key: {e}")
            
            # Connect
            self._client.connect(
                hostname=self.host,
                port=self.port,
                username=self.user,
                pkey=private_key,
                timeout=self.timeout,
                look_for_keys=False,  # Only use provided key
                allow_agent=False     # Don't use SSH agent
            )
            
            logger.info("SSH connection established successfully")
            return True
            
        except AuthenticationException as e:
            logger.error(f"Authentication failed: {e}")
            raise SSHConnectionError(f"Authentication failed: {e}")
        except NoValidConnectionsError as e:
            logger.error(f"Connection failed: {e}")
            raise SSHConnectionError(f"Cannot connect to {self.host}:{self.port}")
        except SSHException as e:
            logger.error(f"SSH error: {e}")
            raise SSHConnectionError(f"SSH error: {e}")
        except Exception as e:
            logger.error(f"Unexpected connection error: {e}")
            raise SSHConnectionError(f"Connection error: {e}")
    
    def disconnect(self) -> None:
        """Close SSH connection and cleanup resources."""
        if self._client is not None:
            logger.info("Disconnecting SSH connection")
            self._client.close()
            self._client = None
    
    def is_connected(self) -> bool:
        """Check if SSH connection is active.
        
        Returns:
            True if connected and transport is active, False otherwise
        """
        if self._client is None:
            return False
        
        transport = self._client.get_transport()
        return transport is not None and transport.is_active()
    
    def execute_command(
        self, 
        command: str, 
        timeout: Optional[int] = None
    ) -> Tuple[str, str, int]:
        """Execute command on remote host.
        
        Args:
            command: Command to execute
            timeout: Command timeout in seconds (None for no timeout)
            
        Returns:
            Tuple of (stdout, stderr, exit_code)
            
        Raises:
            SSHConnectionError: If not connected or execution fails
        """
        if not self.is_connected():
            raise SSHConnectionError("Not connected to remote host")
        
        try:
            logger.info(f"Executing command: {command}")
            
            # Execute command
            stdin, stdout, stderr = self._client.exec_command(
                command, 
                timeout=timeout
            )
            
            # Read output
            stdout_data = stdout.read().decode('utf-8')
            stderr_data = stderr.read().decode('utf-8')
            exit_code = stdout.channel.recv_exit_status()
            
            logger.debug(f"Command exit code: {exit_code}")
            if stderr_data:
                logger.warning(f"Command stderr: {stderr_data}")
                
            return stdout_data, stderr_data, exit_code
            
        except Exception as e:
            logger.error(f"Command execution failed: {e}")
            raise SSHConnectionError(f"Command execution failed: {e}")
    
    def execute_command_simple(self, command: str) -> Optional[str]:
        """Execute command and return only stdout (for backward compatibility).
        
        Args:
            command: Command to execute
            
        Returns:
            Command stdout output or None if failed
        """
        try:
            stdout, stderr, exit_code = self.execute_command(command)
            return stdout if exit_code == 0 else None
        except SSHConnectionError:
            return None
    
    def __enter__(self) -> "SSHConnection":
        """Context manager entry."""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        self.disconnect()
    
    def __repr__(self) -> str:
        """String representation of connection."""
        status = "connected" if self.is_connected() else "disconnected"
        return f"SSHConnection({self.user}@{self.host}:{self.port}, {status})"