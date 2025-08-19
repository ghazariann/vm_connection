#!/usr/bin/env python3
"""Test script for the reconnect method."""

import logging
import time
from vm_connection import SSHConnection
from vm_connection.connection import SSHConnectionError

# Enable logging to see reconnection attempts
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

def main():
    """Test the reconnect functionality."""
    print("Testing reconnect method")
    print("=" * 40)
    
    # Create connection
    conn = SSHConnection(
        host="192.168.215.3",
        user="debian", 
        key_path="/root/.ssh/debian_vm_key"
    )
    
    try:
        # Initial connection
        print("1. Initial connection...")
        conn.connect()
        print(f"   Connected: {conn.is_connected()}")
        
        # Test a command to verify connection works
        result = conn.execute("echo 'Initial connection test'", verbose=False)
        print(f"   Test command result: {result.stdout.strip()}")
        
        # Simulate connection loss by manually disconnecting
        print("\n2. Simulating connection loss...")
        conn.disconnect()
        print(f"   Connected: {conn.is_connected()}")
        
        # Test reconnect with default settings
        print("\n3. Testing reconnect with default settings (3 retries, 2s delay)...")
        success = conn.reconnect()
        print(f"   Reconnect successful: {success}")
        print(f"   Connected: {conn.is_connected()}")
        
        if success:
            # Test command after reconnection
            result = conn.execute("echo 'After reconnection test'", verbose=False)
            print(f"   Test command after reconnect: {result.stdout.strip()}")
        
        
        # Test reconnect to unreachable host (this should fail)
        print("\n5. Testing reconnect to unreachable host...")
        unreachable_conn = SSHConnection(
            host="192.168.255.254",  # Likely unreachable
            user="test",
            key_path="/root/.ssh/debian_vm_key"
        )
        
        try:
            unreachable_conn.reconnect(max_retries=2, delay_seconds=0.5)
            print("   Unexpectedly succeeded!")
        except SSHConnectionError as e:
            print(f"   Expected failure: {e}")
        
        # Clean up
        conn.disconnect()
        print("\n6. Test completed successfully!")
        
    except Exception as e:
        print(f"Error during test: {e}")
        return False
    
    return True

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)