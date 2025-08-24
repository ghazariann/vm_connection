#!/usr/bin/env python3
"""Test long-running commands with execute_long method."""

import logging
from vm_connection.connection import SSHConnection

logging.basicConfig(level=logging.INFO)


if __name__ == "__main__":
    print("\n=== Testing Network Disruptive Command ===")
    
    """Test execute_long with a normal command that takes time."""
    print("=== Testing Normal Long Command ===")
    
    conn = SSHConnection(
        host="192.168.215.3",
        user="debian", 
        key_path="/root/.ssh/debian_vm_key"
    )
    
    try:
        conn.connect()
        print(f"Connected: {conn.is_connected()}")
        
        # Test a simple long command
        print("Running: ./cloudLinux/long_test.sh normal")
        result = conn.execute_long("./cloudLinux/long_test.sh normal", timeout=120, verbose=True)
        
        print(f"Exit code: {result.exit_code}")
        # print(f"Output length: {len(result.stdout)} chars")
        print("Command completed successfully!")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.disconnect()
        
    conn = SSHConnection(
        host="192.168.215.3",
        user="debian", 
        key_path="/root/.ssh/debian_vm_key"
    )
    
    try:
        conn.connect()
        print(f"Connected: {conn.is_connected()}")
        
        # Test a command that temporarily disrupts network
        print("Running: ./cloudLinux/long_test.sh")
        result = conn.execute_long("./cloudLinux/long_test.sh", timeout=180, verbose=True)
        
        print(f"Exit code: {result.exit_code}")
        print(f"Output length: {len(result.stdout)} chars")
        print("Network disruptive command completed successfully!")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.disconnect()