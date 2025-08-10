"""Tests for SSHConnection class."""

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from vm_connection import SSHConnection
from vm_connection.ssh_connection import SSHConnectionError


class TestSSHConnection:
    """Test cases for SSHConnection class."""
    
    def test_init_valid_key(self):
        """Test SSHConnection initialization with valid key file."""
        with tempfile.NamedTemporaryFile(delete=False) as temp_key:
            temp_key.write(b"fake key content")
            temp_key.flush()
            
            conn = SSHConnection(
                host="192.168.1.10",
                user="testuser",
                key_path=temp_key.name
            )
            
            assert conn.host == "192.168.1.10"
            assert conn.user == "testuser"
            assert conn.key_path == Path(temp_key.name)
            assert conn.port == 22
            assert conn.timeout == 30
            assert not conn.is_connected()
            
            Path(temp_key.name).unlink()  # cleanup
    
    def test_init_invalid_key_path(self):
        """Test SSHConnection initialization with invalid key path."""
        with pytest.raises(SSHConnectionError, match="Private key file not found"):
            SSHConnection(
                host="192.168.1.10",
                user="testuser",
                key_path="/nonexistent/key"
            )
    
    def test_init_with_custom_port_and_timeout(self):
        """Test SSHConnection initialization with custom parameters."""
        with tempfile.NamedTemporaryFile(delete=False) as temp_key:
            temp_key.write(b"fake key")
            temp_key.flush()
            
            conn = SSHConnection(
                host="192.168.1.10",
                user="testuser",
                key_path=temp_key.name,
                port=2222,
                timeout=60
            )
            
            assert conn.port == 2222
            assert conn.timeout == 60
            Path(temp_key.name).unlink()
    
    @patch('vm_connection.ssh_connection.paramiko.SSHClient')
    @patch('vm_connection.ssh_connection.paramiko.RSAKey')
    def test_connect_success(self, mock_rsa_key, mock_ssh_client):
        """Test successful SSH connection."""
        with tempfile.NamedTemporaryFile(delete=False) as temp_key:
            temp_key.write(b"fake key")
            temp_key.flush()
            
            # Setup mocks
            mock_key = Mock()
            mock_rsa_key.from_private_key_file.return_value = mock_key
            
            mock_client = Mock()
            mock_ssh_client.return_value = mock_client
            
            conn = SSHConnection(
                host="192.168.1.10",
                user="testuser",
                key_path=temp_key.name
            )
            
            result = conn.connect()
            
            assert result is True
            assert conn._client is mock_client
            mock_client.connect.assert_called_once()
            
            Path(temp_key.name).unlink()
    
    @patch('vm_connection.ssh_connection.paramiko.SSHClient')
    @patch('vm_connection.ssh_connection.paramiko.RSAKey')
    def test_connect_authentication_failure(self, mock_rsa_key, mock_ssh_client):
        """Test SSH connection with authentication failure."""
        with tempfile.NamedTemporaryFile(delete=False) as temp_key:
            temp_key.write(b"fake key")
            temp_key.flush()
            
            # Setup mocks
            mock_key = Mock()
            mock_rsa_key.from_private_key_file.return_value = mock_key
            
            mock_client = Mock()
            mock_client.connect.side_effect = Exception("Authentication failed")
            mock_ssh_client.return_value = mock_client
            
            conn = SSHConnection(
                host="192.168.1.10",
                user="testuser",
                key_path=temp_key.name
            )
            
            with pytest.raises(SSHConnectionError, match="Connection error"):
                conn.connect()
            
            Path(temp_key.name).unlink()
    
    def test_disconnect(self):
        """Test disconnection functionality."""
        with tempfile.NamedTemporaryFile(delete=False) as temp_key:
            temp_key.write(b"fake key")
            temp_key.flush()
            
            conn = SSHConnection(
                host="192.168.1.10",
                user="testuser",
                key_path=temp_key.name
            )
            
            # Mock client
            mock_client = Mock()
            conn._client = mock_client
            
            conn.disconnect()
            
            mock_client.close.assert_called_once()
            assert conn._client is None
            
            Path(temp_key.name).unlink()
    
    def test_is_connected_false_when_no_client(self):
        """Test is_connected returns False when no client."""
        with tempfile.NamedTemporaryFile(delete=False) as temp_key:
            temp_key.write(b"fake key")
            temp_key.flush()
            
            conn = SSHConnection(
                host="192.168.1.10",
                user="testuser",
                key_path=temp_key.name
            )
            
            assert not conn.is_connected()
            Path(temp_key.name).unlink()
    
    def test_is_connected_checks_transport(self):
        """Test is_connected checks transport status."""
        with tempfile.NamedTemporaryFile(delete=False) as temp_key:
            temp_key.write(b"fake key")
            temp_key.flush()
            
            conn = SSHConnection(
                host="192.168.1.10",
                user="testuser",
                key_path=temp_key.name
            )
            
            # Mock client with active transport
            mock_transport = Mock()
            mock_transport.is_active.return_value = True
            
            mock_client = Mock()
            mock_client.get_transport.return_value = mock_transport
            conn._client = mock_client
            
            assert conn.is_connected()
            Path(temp_key.name).unlink()
    
    def test_execute_command_when_not_connected(self):
        """Test command execution when not connected."""
        with tempfile.NamedTemporaryFile(delete=False) as temp_key:
            temp_key.write(b"fake key")
            temp_key.flush()
            
            conn = SSHConnection(
                host="192.168.1.10",
                user="testuser",
                key_path=temp_key.name
            )
            
            with pytest.raises(SSHConnectionError, match="Not connected"):
                conn.execute_command("ls -la")
                
            Path(temp_key.name).unlink()
    
    def test_execute_command_simple_not_connected(self):
        """Test simple command execution when not connected."""
        with tempfile.NamedTemporaryFile(delete=False) as temp_key:
            temp_key.write(b"fake key")
            temp_key.flush()
            
            conn = SSHConnection(
                host="192.168.1.10",
                user="testuser",
                key_path=temp_key.name
            )
            
            result = conn.execute_command_simple("ls -la")
            assert result is None
            
            Path(temp_key.name).unlink()
    
    def test_repr(self):
        """Test string representation."""
        with tempfile.NamedTemporaryFile(delete=False) as temp_key:
            temp_key.write(b"fake key")
            temp_key.flush()
            
            conn = SSHConnection(
                host="192.168.1.10",
                user="testuser",
                key_path=temp_key.name
            )
            
            repr_str = repr(conn)
            assert "SSHConnection(testuser@192.168.1.10:22, disconnected)" == repr_str
            
            Path(temp_key.name).unlink()
    
    @patch('vm_connection.ssh_connection.paramiko.SSHClient')
    @patch('vm_connection.ssh_connection.paramiko.RSAKey')
    def test_context_manager(self, mock_rsa_key, mock_ssh_client):
        """Test using SSHConnection as context manager."""
        with tempfile.NamedTemporaryFile(delete=False) as temp_key:
            temp_key.write(b"fake key")
            temp_key.flush()
            
            # Setup mocks
            mock_key = Mock()
            mock_rsa_key.from_private_key_file.return_value = mock_key
            
            mock_client = Mock()
            mock_ssh_client.return_value = mock_client
            
            conn = SSHConnection(
                host="192.168.1.10",
                user="testuser",
                key_path=temp_key.name
            )
            
            with conn:
                # Connect should have been called
                mock_client.connect.assert_called_once()
            
            # Disconnect should have been called
            mock_client.close.assert_called_once()
            
            Path(temp_key.name).unlink()