"""Shared pytest fixtures for vm_connection tests."""

import pytest
from unittest.mock import Mock
import tempfile
import os

from vm_connection.connection import SSHConnection


@pytest.fixture(scope="session")
def temp_key_file():
    """Create a temporary SSH key file for entire test session."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.pem', delete=False) as f:
        f.write("-----BEGIN RSA PRIVATE KEY-----\n")
        f.write("fake_key_content_for_testing\n") 
        f.write("-----END RSA PRIVATE KEY-----\n")
        temp_path = f.name
    
    yield temp_path
    
    # Cleanup once at end of session
    if os.path.exists(temp_path):
        os.unlink(temp_path)


@pytest.fixture
def ssh_connection(temp_key_file):
    """Create SSHConnection instance for testing."""
    return SSHConnection(
        host="test-host",
        user="test-user",
        key_path=temp_key_file,
        port=22,
        timeout=30
    )


@pytest.fixture
def mock_channel_setup():
    """Create commonly used mock objects for SSH channel testing."""
    from unittest.mock import patch, Mock
    
    with patch('vm_connection.connection.paramiko.SSHClient') as mock_ssh_client, \
         patch('vm_connection.connection.paramiko.RSAKey') as mock_rsa_key:
        
        mock_client = Mock()
        mock_transport = Mock()
        mock_channel = Mock()
        
        # Setup patched objects
        mock_ssh_client.return_value = mock_client
        mock_rsa_key.from_private_key_file.return_value = Mock()
        
        # Setup basic connections
        mock_client.get_transport.return_value = mock_transport
        mock_transport.is_active.return_value = True
        mock_transport.open_session.return_value = mock_channel
        
        # Default channel behavior
        mock_channel.recv_stderr_ready.return_value = False
        mock_channel.exit_status_ready.return_value = True
        mock_channel.recv_exit_status.return_value = 0
        mock_channel.settimeout = Mock()
        mock_channel.exec_command = Mock()
        mock_channel.close = Mock()
        
        yield {
            'client': mock_client,
            'transport': mock_transport, 
            'channel': mock_channel
        }