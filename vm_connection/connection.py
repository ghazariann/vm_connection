"""SSH Connection module for connecting to remote Linux VMs."""

import logging
import time
import socket
import uuid
from pathlib import Path
from dataclasses import dataclass
from typing import Callable, Optional
from functools import wraps
from .stream import LineEmitter, default_printer, StreamName 
from .health import icmp_probe, tcp_probe, IsAliveResult
from .reboot import BootIdentity, compare_boot_identities
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

import paramiko
from paramiko.ssh_exception import (
    AuthenticationException,
    NoValidConnectionsError,
    SSHException,
)

logger = logging.getLogger(__name__)

@dataclass
class ExecResult:
    stdout: str
    stderr: str
    exit_code: int

# SSHConnectionError and other exceptions are now imported from .exceptions
             

class SSHConnection:
    """Handles SSH connections to remote Linux VMs using paramiko.
    This class provides a high-level interface for SSH connections with:
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
        self._last_log_file = None
        self._last_exit_code_file = None
        
        # Validate key file exists
        if not self.key_path.exists():
            raise KeyFileNotFoundError(f"Private key file not found: {key_path}")
        
    def connect(self) -> bool:
        """Establish SSH connection using private key authentication.
        Returns:
            True if connection successful, False otherwise      
        Raises:
            SSHConnectionError: For authentication or connection failures
        """
        if self._client is not None:
            self.disconnect()
        
        try:
            logger.info(f"Connecting to {self.user}@{self.host}:{self.port}")
            
            # Create SSH client
            self._client = paramiko.SSHClient()
       
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
                allow_agent=False     # Don't use SSH agent, which caches the decrypted key in memory
            )
            
            logger.info("SSH connection established successfully")
            return True
            
        except AuthenticationException as e:
            logger.error(f"Authentication failed: {e}")
            raise AuthenticationFailedError(f"Authentication failed: {e}")
        except NoValidConnectionsError as e:
            logger.error(f"Connection failed: {e}")
            raise HostUnreachableError(f"Cannot connect to {self.host}:{self.port}")
        except SSHException as e:
            logger.error(f"SSH error: {e}")
            raise SSHConnectionError(f"SSH error: {e}")
        except Exception as e:
            logger.error(f"Unexpected connection error: {e}")
            raise UnexpectedError(f"Connection error: {e}")
    
    def disconnect(self) -> None:
        """Close SSH connection and cleanup resources."""
        if self._client is not None:
            # logger.info("Disconnecting SSH connection")
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
        # Check if transport is None or not active
        if transport is None or not transport.is_active():
            return False
        # but transport can be still in memory and show as active
        # try to send/receive data to verify the transport is still valid
        try:
            # Use send_ignore() which sends a SSH_MSG_IGNORE packet to test connectivity
            transport.send_ignore()
            return True
        except (socket.error, EOFError, OSError):
            return False
    def is_alive(self) -> "IsAliveResult":
        """
        Layered liveness:
        1) SSH transport state (reason only; strongest signal if present)
        2) TCP service-port scan (defaults [22, 443, 80], configurable)
        3) ICMP reachability (final check)
        No early returns: accumulate reasons and decide at the end.
        """
        reasons = {}

        # Step 1: Check SSH transport state
        ssh_is_connected = self.is_connected()
        reasons["ssh"] = "up" if ssh_is_connected else "down"

        # Step 2: Check TCP service ports (default: [22, 443, 80])
        default_ports = [22, 80, 443]
        tcp_results = []
        for p in default_ports:
            t = tcp_probe(self.host, p)
            tcp_results.append(t)
            reasons[f"tcp:{p}"] = t.reason

        # Step 3: Check ICMP reachability (Ping)
        icmp_is_ok = icmp_probe(self.host)
        reasons["icmp"] = icmp_is_ok.reason

        # Combine results: If any layer indicates the VM is alive, it's considered operational
        alive = ssh_is_connected or any(tcp_is_ok.ok for tcp_is_ok in tcp_results) or icmp_is_ok.ok
        return IsAliveResult(alive=alive, reasons=reasons)
    
    def reconnect(self, max_retries: int = 3, delay_seconds: float = 2.0) -> bool:
        """Attempt to re-establish a lost SSH connection with retries.
        
        This method will disconnect any existing connection and then attempt
        to reconnect with configurable retry logic.
        
        Args:
            max_retries: Maximum number of connection attempts (default: 3)
            delay_seconds: Delay between retry attempts in seconds (default: 2.0)
            
        Returns:
            True if reconnection successful, False if all retries failed
            
        Raises:
            SSHConnectionError: If all reconnection attempts fail
        """
        logger.info(f"Starting reconnection to {self.user}@{self.host}:{self.port}")

        last_error = None
        
        for attempt in range(1, max_retries + 1):
            try:
                logger.info(f"Reconnection attempt {attempt}/{max_retries}")
                
                # Check if host is alive before attempting SSH connection
                alive_check = self.is_alive()
                if not alive_check.alive:
                    logger.warning(f"Host appears unreachable: {alive_check.reasons}")
                    # Still try to connect in case health check is wrong
                
                # Attempt to connect
                success = self.connect()
                if success and self.is_connected():
                    logger.info(f"Reconnection successful on attempt {attempt}")
                    return True
            
            except SSHConnectionError as e:
                last_error = e
                logger.warning(f"Reconnection attempt {attempt} failed: {e}")
                
            except Exception as e:
                last_error = SSHConnectionError(f"Unexpected error during reconnection: {e}")
                logger.error(f"Unexpected error on attempt {attempt}: {e}")
            
            # Wait before next attempt (except after the last attempt)
            if attempt < max_retries:
                logger.info(f"Waiting {delay_seconds} seconds before next attempt")
                time.sleep(delay_seconds)
        
        # All attempts failed
        error_msg = f"Failed to reconnect after {max_retries} attempts"
        if last_error:
            error_msg += f". Last error: {last_error}"
            
        logger.error(error_msg)
        raise SSHConnectionError(error_msg)

    @staticmethod
    def resilient(method):
        """
        Decorator for SSHConnection instance methods:
        - Handles SSH connection failures, attempts to reconnect, and continues the task without re-running.
        - Takes a boot identity snapshot before calling the method.
        - If SSH connection fails, it attempts reconnection.
        - After reconnection, it verifies the result by checking the log file and exit code, without re-running the task.
        """
        @wraps(method)
        def wrapper(self, *args, **kwargs):
            try:
                before = self.snapshot_boot_identity()
                result = method(self, *args, **kwargs)
                self.assert_same_boot(before)  # Compare boot IDs
                return result
            except Exception as e:
                logger.info(f"Connection error detected: {e}. Attempting to reconnect.")
                if self.reconnect(max_retries=5, delay_seconds=2):
                    logger.info("Reconnected successfully. Checking for reboot...")
                    self.assert_same_boot(before)  # Compare boot ID again after reconnect
                    logger.info("Verifying result after reconnect...")
                    # Return the result by checking the log file and exit code (without re-running the command)
                    if self._last_log_file and self._last_exit_code_file:  
                        result = self._verify_result_from_logs(self._last_log_file, self._last_exit_code_file)
                        self._last_log_file, self._last_exit_code_file = None, None  # Clear after use
                        return result  
                    else:
                        logger.error("No log file available for verification.")
                        raise SSHConnectionError("No log file or exit code file available for verification.")
                else:
                    logger.error(f"Reconnection failed after multiple attempts: {e}")
                    raise e  # Raise the original exception if reconnect fails
        return wrapper
    
    @resilient
    def execute(self, command: str, output_callback: Optional[Callable[[str, StreamName], None]] = None, timeout: float = 60.0, inactivity_timeout: float = 10.0, verbose: bool = True) -> ExecResult:
        return self._execute_core(command, output_callback, timeout, inactivity_timeout, verbose)

    def _execute_core(self, command: str, output_callback: Optional[Callable[[str, StreamName], None]] = None, timeout: float = 60.0, inactivity_timeout: float = 10.0, verbose: bool = True) -> ExecResult:
        """
        Run a command with real-time streaming.
        Args:
            command: Command to execute remotely.
            output_callback: Optional `fn(line, stream)`; if not provided and `verbose=True`,
                            a default printer is used; if `verbose=False`, output is captured.
            timeout: Maximum allowed time for the entire command execution without any output.
            inactivity_timeout: Maximum allowed inactivity time since last output.
            verbose: If True and no callback is supplied, prints lines live to console.
        Returns:
            ExecResult(stdout, stderr, exit_code)
        """
        
        read_chunk_size = 4096  # Size of data chunks to read from the channel
        if not self.is_connected():
            raise SSHConnectionError("Not connected to remote host")

        transport = self._client.get_transport()
        if transport is None or not transport.is_active():
            raise SSHConnectionError("SSH transport is not active")

        chan = transport.open_session()
        try:
            chan.exec_command(command)
            chan.settimeout(0.0)  # non-blocking

            # Choose the effective callback
            effective_cb = output_callback if output_callback else (default_printer if verbose else None)

            out_em = LineEmitter(effective_cb, "stdout")
            err_em = LineEmitter(effective_cb, "stderr")

            start_time = time.monotonic()
            last_activity_time = start_time  # To track the last output time

            # Start checking for overall timeout
            while True:
                # Check for new output
                if chan.recv_ready():
                    data = chan.recv(read_chunk_size)
                    if data:
                        out_em.feed(data.decode("utf-8", errors="replace"))
                        last_activity_time = time.monotonic()  # Reset inactivity timer

                if chan.recv_stderr_ready():
                    data = chan.recv_stderr(read_chunk_size)
                    if data:
                        err_em.feed(data.decode("utf-8", errors="replace"))
                        last_activity_time = time.monotonic()  # Reset inactivity timer

                current_time = time.monotonic()

                # Check if the overall timeout is exceeded (before any result is received)
                if (current_time - start_time) > timeout and last_activity_time == start_time:
                    chan.close()
                    raise OverallTimeoutError(f"Exceeded overall timeout of {timeout} seconds")

                # Check for inactivity timeout (no output for a certain period)
                if (current_time - last_activity_time) > inactivity_timeout:
                    # logger.warning(f"Inactivity timeout of {inactivity_timeout} seconds reached. Checking connection.")
                    if not self.is_connected():
                        chan.close()
                        raise LostConnectionDuringExecutionError("Lost connection during command execution.")

                # If the command has finished executing and no more output is available
                if chan.exit_status_ready() and not chan.recv_ready() and not chan.recv_stderr_ready():
                    break

            out_em.flush()
            err_em.flush()
            exit_code = chan.recv_exit_status()

            return ExecResult(stdout=out_em.collected(), stderr=err_em.collected(), exit_code=exit_code)
        
        except (OverallTimeoutError, LostConnectionDuringExecutionError):
            raise  # Re-raise these specific exceptions
        except Exception as e:
            logger.error("Streaming exec failed: %s", e)
            raise CommandExecutionFailedError(f"Streaming command execution failed: {e}") from e
        finally:
            chan.close()
        
    def snapshot_boot_identity(self, timeout: float = 3.0) -> BootIdentity:
        """Capture the VM's boot fingerprint (tiered: boot_id → btime)."""
        if not self.is_connected():
            raise SSHConnectionError("Not connected")

        # Try boot_id first
        result = self._execute_core(
            "cat /proc/sys/kernel/random/boot_id 2>/dev/null || true", verbose=False
        )
        out, err, code = result.stdout, result.stderr, result.exit_code
        boot_id = out.strip() if (code == 0 and out.strip()) else None
        
        if boot_id:
            return BootIdentity(boot_id=boot_id, btime=None)

        # Fallback: btime
        result = self._execute_core(
            "awk '/^btime /{print $2}' /proc/stat 2>/dev/null || true", verbose=False
        )
        out, err, code = result.stdout, result.stderr, result.exit_code
        btime = int(out.strip()) if out.strip().isdigit() else None
        return BootIdentity(boot_id=None, btime=btime)

    def _generate_log_files(self) -> tuple[str, str, str]:
        """Generate unique log file paths for nohup execution."""
        unique_id = str(uuid.uuid4())[:8]
        log_file = f"/tmp/nohup_{unique_id}.log"
        exit_code_file = f"{log_file}.exit"
        return log_file, exit_code_file

    def _verify_result_from_logs(self, log_file: str, exit_code_file: str) -> ExecResult:
        """
        Verifies the result of the command by reading the log and exit code file.
        This method is called after reconnecting to check if the command completed successfully.
        """

        # Stream the log file until the exit code is available
        out_em = LineEmitter(default_printer, "stdout")  # Create a LineEmitter to collect output
        last_size = 0  # Track the last known size of the log file

        # Start streaming the log file while the exit code is not available
        while True:
            # Check for exit code file
            exit_result = self._execute_core(f"cat {exit_code_file} 2>/dev/null || echo ''", verbose=False, timeout=5.0)
            exit_code = int(exit_result.stdout.strip()) if exit_result.stdout.strip().isdigit() else None

            # Stream the log file if the exit code is still not found
            if exit_code is None:
                log_result = self._execute_core(f"cat {log_file} 2>/dev/null || echo ''", verbose=False, timeout=5.0)
                # print(log_result)
                current_content = log_result.stdout

                # If new content has been added to the log file, feed it to the emitter
                if len(current_content) > last_size:
                    new_content = current_content[last_size:]
                    out_em.feed(new_content)
                    last_size = len(current_content)

                # Sleep for a short interval before checking again
                time.sleep(0.5)
            else:
                break  # Exit the loop if the exit code is found

        # Once the exit code is available, collect the final log content
        log_result = self._execute_core(f"cat {log_file} 2>/dev/null || echo ''", verbose=False, timeout=10.0)
        log_content = log_result.stdout.strip()

        # Return the result as an ExecResult
        if exit_code == 0:
            logger.info("Command completed successfully")
        else:
            logger.error(f"Command failed with exit code {exit_code}: {log_content}")

        # Cleanup the log and exit code files
        self._execute_core(f"rm -f {log_file} {exit_code_file}", verbose=False, timeout=5.0)

        # Return the result
        return ExecResult(stdout=log_content, stderr="", exit_code=exit_code)

        
    def assert_same_boot(self, before: BootIdentity, timeout: float = 3.0) -> None:
        """Check if boot identity changed since `before`."""
        after = self.snapshot_boot_identity(timeout=timeout)
        compare_boot_identities(before, after)
        
    def __enter__(self) -> "SSHConnection":
        """Context manager entry."""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        self.disconnect()
    
    @resilient
    def execute_long(self, command: str, output_callback: Optional[Callable[[str, StreamName], None]] = None, poll_interval: float = 1.0, timeout: float = 3600.0, verbose: bool = True, last_known_size: int = 0) -> ExecResult:
        """
        Execute a long-running command using nohup that survives SSH disconnections.
        This method is decorated with `reconnect_and_stream` to handle reconnection and
        resume file streaming if the SSH connection is lost.

        Args:
            command: Command to execute remotely
            output_callback: Optional callback for streaming output
            poll_interval: How often to poll the log file for new content (seconds)
            timeout: Maximum time to wait for command completion (seconds)
            verbose: Whether to print output live
            last_known_size: The last known size of the log file, used to resume streaming

        Returns:
            ExecResult with stdout, stderr, and exit code
        """
        # Generate unique log file paths
        self._last_log_file, self._last_exit_code_file = self._generate_log_files()
        # Wrap the command with nohup and logging
        wrapped_command = (
            f"nohup bash -c '"
            f"({command}) > { self._last_log_file} 2>&1; "
            f"echo $? > {self._last_exit_code_file}"
            f"' >/dev/null 2>&1 &"
        )
        # Start the nohup command
        self._execute_core(wrapped_command, verbose=False, inactivity_timeout=5)

        # Wait a moment for the process to start
        time.sleep(0.5)

        # Stream the log file until completion, resuming from the last known size
        return self._stream_log_file( self._last_log_file, self._last_exit_code_file, output_callback, poll_interval, timeout, verbose)
    
    def _stream_log_file(self, log_file: str, exit_code_file: str, output_callback: Optional[Callable[[str, StreamName], None]] = None, poll_interval: float = 1.0, timeout: float = 3600.0, verbose: bool = True) -> ExecResult:
        """
        Stream contents of a log file until the command completes.
        
        Args:
            log_file: Path to the log file to stream
            exit_code_file: Path to file containing exit code when command completes
            output_callback: Optional callback for output lines
            poll_interval: How often to check for new content
            timeout: Maximum time to wait
            verbose: Whether to print output live
            
        Returns:
            ExecResult with collected output and exit code
        """
        effective_cb = output_callback if output_callback else (default_printer if verbose else None)
        out_em = LineEmitter(effective_cb, "stdout")
        
        start_time = time.monotonic()
        last_size = 0
        
        while True:
            current_time = time.monotonic()
            
            # Check timeout
            if (current_time - start_time) > timeout:
                raise TimeoutError(f"Long command exceeded timeout of {timeout} seconds")
            
            # Check if command completed by looking for exit code file
            exit_result = self._execute_core(f"cat {exit_code_file} 2>/dev/null || echo ''", verbose=False, timeout=5.0)
            if exit_result.stdout.strip().isdigit():
                exit_code = int(exit_result.stdout.strip())
                
                # Get final output
                final_result = self._execute_core(f"cat {log_file} 2>/dev/null || echo ''", verbose=False, timeout=10.0)
                remaining_content = final_result.stdout[last_size:] if len(final_result.stdout) > last_size else ""
                if remaining_content:
                    out_em.feed(remaining_content)
                
                out_em.flush()
                
                # Cleanup files
                self._execute_core(f"rm -f {log_file} {exit_code_file} {log_file}.pid", verbose=False, timeout=5.0)
                
                return ExecResult(stdout=out_em.collected(), stderr="", exit_code=exit_code)
            
            # Get current log file content
            log_result = self._execute_core(f"cat {log_file} 2>/dev/null || echo ''", verbose=False, timeout=5.0)
            current_content = log_result.stdout
            
            # Stream new content if any
            if len(current_content) > last_size:
                new_content = current_content[last_size:]
                out_em.feed(new_content)
                last_size = len(current_content)
            # Wait before next poll
            time.sleep(poll_interval)

    def __repr__(self) -> str:
        """String representation of connection."""
        status = "connected" if self.is_connected() else "disconnected"
        return f"SSHConnection({self.user}@{self.host}:{self.port}, {status})"