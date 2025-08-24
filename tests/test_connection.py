"""Pytest tests for SSHConnection class without requiring live VM."""

import pytest
from unittest.mock import Mock, patch, MagicMock
import tempfile
import os
from pathlib import Path
import socket
import time

from vm_connection.connection import SSHConnection, ExecResult
from vm_connection.exceptions import (
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
import paramiko.ssh_exception


class TestSSHConnection:
    """Test SSHConnection class functionality."""
    
    # Fixtures moved to conftest.py

    def test_ssh_connection_init_success(self, temp_key_file):
        """Test successful SSHConnection initialization."""
        conn = SSHConnection(
            host="test-host",
            user="test-user", 
            key_path=temp_key_file
        )
        
        assert conn.host == "test-host"
        assert conn.user == "test-user"
        assert conn.port == 22
        assert conn.timeout == 30
        assert conn._client is None

    def test_ssh_connection_init_missing_key_file(self):
        """Test SSHConnection initialization with missing key file."""
        with pytest.raises(KeyFileNotFoundError, match="Private key file not found"):
            SSHConnection(
                host="test-host",
                user="test-user",
                key_path="/nonexistent/key.pem"
            )

    @patch('vm_connection.connection.paramiko.SSHClient')
    @patch('vm_connection.connection.paramiko.RSAKey')
    def test_connect_success(self, mock_rsa_key, mock_ssh_client, ssh_connection):
        """Test successful SSH connection."""
        # Arrange
        mock_client = Mock()
        mock_ssh_client.return_value = mock_client
        mock_key = Mock()
        mock_rsa_key.from_private_key_file.return_value = mock_key
        
        # Act
        result = ssh_connection.connect()
        
        # Assert
        assert result is True
        mock_client.connect.assert_called_once_with(
            hostname="test-host",
            port=22,
            username="test-user",
            pkey=mock_key,
            timeout=30,
            look_for_keys=False,
            allow_agent=False
        )

    @pytest.mark.parametrize("expected_custom_exception,expected_message", [
        (AuthenticationFailedError, "Authentication failed"),
        (HostUnreachableError, "Cannot connect to"), 
        (SSHConnectionError, "SSH error"),
        (UnexpectedError, "Connection error"),
    ])
    @patch('vm_connection.connection.paramiko.SSHClient')
    @patch('vm_connection.connection.paramiko.RSAKey')
    def test_connect_failed(self, mock_rsa_key, mock_ssh_client, ssh_connection, 
                           expected_custom_exception, expected_message):
        """Test SSH connection failures - expect custom exceptions to be raised."""
        # Arrange
        mock_client = Mock()
        mock_ssh_client.return_value = mock_client
        mock_key = Mock()
        mock_rsa_key.from_private_key_file.return_value = mock_key
        
        # Map expected exceptions to the paramiko exceptions that trigger them
        if expected_custom_exception == AuthenticationFailedError:
            mock_client.connect.side_effect = paramiko.ssh_exception.AuthenticationException("Invalid key")
        elif expected_message == "Cannot connect to":
            mock_client.connect.side_effect = paramiko.ssh_exception.NoValidConnectionsError({("test-host", 22): "Host unreachable"})
        elif expected_message == "SSH error":
            mock_client.connect.side_effect = paramiko.ssh_exception.SSHException("Protocol error")
        else:  # "Connection error"
            mock_client.connect.side_effect = Exception("Unexpected error")
        
        # Act & Assert - expect your custom exception to be raised
        with pytest.raises(expected_custom_exception, match=expected_message):
            ssh_connection.connect()

    @pytest.mark.parametrize("stdout_data,stderr_data,exit_code", [
        ("Command output\n", "", 0),  # Success case
        ("", "bash: file.txt: No such file or directory\n", 1),  # Error case
        ("Line 1\nLine 2\n", "Warning: deprecated\n", 0),  # Both outputs
    ])
    def test_execute_core(self, ssh_connection, mock_channel_setup, stdout_data, stderr_data, exit_code):
        """Test _execute_core method with various output scenarios."""        
        channel = mock_channel_setup['channel']
        
        # Setup stdout/stderr data
        stdout_chunks = [stdout_data.encode()] if stdout_data else []
        stderr_chunks = [stderr_data.encode()] if stderr_data else []
        
        stdout_call_count = 0
        stderr_call_count = 0
        
        def mock_recv_ready():
            nonlocal stdout_call_count
            return stdout_call_count < len(stdout_chunks)
        
        def mock_recv_stderr_ready():
            nonlocal stderr_call_count
            return stderr_call_count < len(stderr_chunks)
            
        def mock_recv(size):
            nonlocal stdout_call_count
            if stdout_call_count < len(stdout_chunks):
                data = stdout_chunks[stdout_call_count]
                stdout_call_count += 1
                return data
            return b''
            
        def mock_recv_stderr(size):
            nonlocal stderr_call_count
            if stderr_call_count < len(stderr_chunks):
                data = stderr_chunks[stderr_call_count]
                stderr_call_count += 1
                return data
            return b''
        
        def mock_exit_status_ready():
            return (stdout_call_count >= len(stdout_chunks) and 
                   stderr_call_count >= len(stderr_chunks))
        
        channel.recv_ready = mock_recv_ready
        channel.recv_stderr_ready = mock_recv_stderr_ready
        channel.recv = mock_recv
        channel.recv_stderr = mock_recv_stderr
        channel.exit_status_ready = mock_exit_status_ready
        channel.recv_exit_status.return_value = exit_code
        
        # Connect first
        ssh_connection.connect()
        
        # Act
        result = ssh_connection._execute_core("test command", verbose=False)
        
        # Assert
        assert isinstance(result, ExecResult)
        assert result.exit_code == exit_code
        assert result.stdout == stdout_data
        assert result.stderr == stderr_data
        channel.exec_command.assert_called_once_with("test command")

    def test_output_callback_streaming(self, ssh_connection, mock_channel_setup, capsys):
        """Test streaming callback functionality with multiple lines from stdout and stderr."""
        channel = mock_channel_setup['channel']
        
        # Setup streaming data - multiple lines that come in over time
        stdout_lines = ["Starting process...\n", "Processing data...\n", "Task completed!\n"]
        stderr_lines = ["Warning: config not found\n", "Error: retry attempt\n"]
        
        stdout_chunks = [line.encode() for line in stdout_lines]
        stderr_chunks = [line.encode() for line in stderr_lines]
        
        stdout_call_count = 0
        stderr_call_count = 0
        
        def mock_recv_ready():
            nonlocal stdout_call_count
            return stdout_call_count < len(stdout_chunks)
            
        def mock_recv_stderr_ready():
            nonlocal stderr_call_count
            return stderr_call_count < len(stderr_chunks)
            
        def mock_recv(size):
            nonlocal stdout_call_count
            if stdout_call_count < len(stdout_chunks):
                data = stdout_chunks[stdout_call_count]
                stdout_call_count += 1
                return data
            return b''
            
        def mock_recv_stderr(size):
            nonlocal stderr_call_count
            if stderr_call_count < len(stderr_chunks):
                data = stderr_chunks[stderr_call_count]
                stderr_call_count += 1
                return data
            return b''
            
        def mock_exit_status_ready():
            # Ready when all chunks have been consumed
            return (stdout_call_count >= len(stdout_chunks) and 
                   stderr_call_count >= len(stderr_chunks))
        
        channel.recv_ready = mock_recv_ready
        channel.recv_stderr_ready = mock_recv_stderr_ready
        channel.recv = mock_recv
        channel.recv_stderr = mock_recv_stderr
        channel.exit_status_ready = mock_exit_status_ready
        channel.recv_exit_status.return_value = 0
        
        # Use a callback that actually prints (like default_printer)
        def printing_callback(line, stream_name):
            # This actually prints to console (like default_printer)
            print(f"[{stream_name}] {line}", end="")
        
        ssh_connection.connect()
        
        # Act
        result = ssh_connection._execute_core("streaming command", output_callback=printing_callback)
        
        # Assert - test that callback actually printed to console
        captured = capsys.readouterr()
        
        # Check what was printed to stdout
        expected_output = (
            "[stdout] Starting process...\n"
            "[stderr] Warning: config not found\n"
            "[stdout] Processing data...\n" 
            "[stderr] Error: retry attempt\n"
            "[stdout] Task completed!\n"
        )
        assert captured.out == expected_output
        
        # Verify final result contains all data
        expected_stdout = "".join(stdout_lines)
        expected_stderr = "".join(stderr_lines)
        assert result.stdout == expected_stdout
        assert result.stderr == expected_stderr
        assert result.exit_code == 0

    def test_command_execution_timeout(self, ssh_connection, mock_channel_setup):
        """Test command execution timeout scenario."""
        channel = mock_channel_setup['channel']
        
        # Simulate no output and command never finishing
        channel.recv_ready.return_value = False
        channel.recv_stderr_ready.return_value = False
        channel.exit_status_ready.return_value = False  # Never finishes
        
        ssh_connection.connect()
        
        # Act & Assert
        with pytest.raises(OverallTimeoutError, match="Exceeded overall timeout"):
            ssh_connection._execute_core("sleep 100", timeout=0.1)  # Very short timeout

    @patch('vm_connection.connection.icmp_probe')
    @patch('vm_connection.connection.tcp_probe')
    def test_network_drop_and_successful_reconnect(self, mock_tcp_probe, mock_icmp_probe, 
                                                  ssh_connection, mock_channel_setup):
        """Test simulating network drop and successful reconnection."""
        # Arrange
        mock_client = mock_channel_setup['client']
        
        # Mock health check responses  
        mock_tcp_probe.return_value = Mock(ok=True, reason="22 ok")
        mock_icmp_probe.return_value = Mock(ok=True, reason="icmp ok")
        
        # Simulate initial connection success, then failure, then success
        connect_call_count = 0
        def mock_connect(*args, **kwargs):
            nonlocal connect_call_count
            connect_call_count += 1
            if connect_call_count == 2:  # Fail on second attempt (first reconnect)
                raise SSHConnectionError({("test-host", 22): "Connection failed"})
            # Success on first and third attempts
        
        mock_client.connect.side_effect = mock_connect
        
        # Initial connection
        ssh_connection.connect()
        
        # Simulate connection drop
        ssh_connection.disconnect()
        
        # Act - attempt reconnection (should succeed on second try)
        result = ssh_connection.reconnect(max_retries=3, delay_seconds=0.1)
        
        # Assert
        assert result is True
        assert connect_call_count >= 2  # At least one retry happened

    def test_resilient_decorator_same_boot_id(self, ssh_connection, mock_channel_setup):
        """Test @resilient decorator with same boot ID - no reboot detected."""
        transport = mock_channel_setup['transport']
        
        # Track executed commands and their responses
        executed_commands = []
        command_responses = {
            "cat /proc/sys/kernel/random/boot_id 2>/dev/null || true": [
                "12345678-1234-1234-1234-123456789012\n",  # First call
                "12345678-1234-1234-1234-123456789012\n"   # Second call (same)
            ],
            "echo 'test command'": ["Test command output\n"]
        }
        command_call_counts = {}
        
        def create_mock_channel():
            channel = Mock()
            
            def mock_exec_command(command):
                executed_commands.append(command)
                
            def mock_recv(*args):
                if not executed_commands:
                    return b''
                
                current_command = executed_commands[-1]
                if current_command not in command_call_counts:
                    command_call_counts[current_command] = 0
                
                call_count = command_call_counts[current_command]
                
                if current_command in command_responses:
                    responses = command_responses[current_command]
                    if call_count < len(responses):
                        data = responses[call_count].encode()
                        command_call_counts[current_command] += 1
                        return data
                return b''
            
            def mock_recv_ready():
                if not executed_commands:
                    return False
                
                current_command = executed_commands[-1]
                if current_command not in command_call_counts:
                    command_call_counts[current_command] = 0
                    
                call_count = command_call_counts[current_command]
                
                if current_command in command_responses:
                    return call_count < len(command_responses[current_command])
                return False
                
            channel.exec_command = mock_exec_command
            channel.recv = mock_recv
            channel.recv_ready = mock_recv_ready
            channel.recv_stderr_ready.return_value = False
            channel.exit_status_ready.return_value = True
            channel.recv_exit_status.return_value = 0
            channel.settimeout = Mock()
            channel.close = Mock()
            
            return channel
        
        transport.open_session.side_effect = create_mock_channel
        
        ssh_connection.connect()
        
        result = ssh_connection.execute("echo 'test command'", verbose=False)
        assert result.exit_code == 0
        assert "Test command output" in result.stdout

    def test_resilient_decorator_different_boot_id(self, ssh_connection, mock_channel_setup):
        """Test @resilient decorator with different boot ID - reboot detected, should raise UnexpectedRebootError."""
        transport = mock_channel_setup['transport']
        
        command_responses = {
            "cat /proc/sys/kernel/random/boot_id 2>/dev/null || true": [
                "12345678-1234-1234-1234-123456789012\n",  # First call
                "12345678-1234-1234-1234-123456789011\n"   # Second call (same)
            ],
            "echo 'test command'": ["Test command output\n"]
        }
        # Track which response to return for each command type
        call_counters = {}
        
        def create_mock_channel():
            channel = Mock()
            channel_data = {}  # Store data for this specific channel/session
            
            def mock_exec_command(command):                
                # Initialize counter for this command type if not exists
                if command not in call_counters:
                    call_counters[command] = 0
                
                # Get the response for this command execution
                if command in command_responses:
                    responses = command_responses[command]
                    if call_counters[command] < len(responses):
                        channel_data['response'] = responses[call_counters[command]].encode()
                        call_counters[command] += 1
                    else:
                        channel_data['response'] = b''
                else:
                    channel_data['response'] = b''
                
                channel_data['response_sent'] = False
                
            def mock_recv(*args):
                if 'response' in channel_data and not channel_data['response_sent']:
                    data = channel_data['response']
                    channel_data['response_sent'] = True
                    return data
                return b''
            
            def mock_recv_ready():
                return 'response' in channel_data and not channel_data['response_sent']
                
            channel.exec_command = mock_exec_command
            channel.recv = mock_recv
            channel.recv_ready = mock_recv_ready
            channel.recv_stderr_ready.return_value = False
            channel.exit_status_ready.return_value = True
            channel.recv_exit_status.return_value = 0
            channel.settimeout = Mock()
            channel.close = Mock()
            
            return channel
        
        transport.open_session.side_effect = create_mock_channel
        
        ssh_connection.connect()
        
        # This should raise UnexpectedRebootError due to different boot IDs
        with pytest.raises(UnexpectedRebootError):
            ssh_connection.execute("echo 'test command'", verbose=False)