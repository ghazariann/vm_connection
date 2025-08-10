#!/usr/bin/env python3
"""Test script for vm_connection library."""

from vm_connection import SSHConnection
from vm_connection.ssh_connection import SSHConnectionError

def main():
    print("Testing VM Connection Library")
    print("=" * 40)
    
    # Test with your VM
    conn = SSHConnection(
        host="192.168.215.3",
        user="debian",
        key_path="/root/.ssh/debian_vm_key",
        timeout=10
    )
    
    print(f"Connection object: {conn}")
    
    try:
        print("Attempting to connect...")
        with conn:
            print("✓ Connected successfully!")
            
            # Test basic command
            stdout, stderr, exit_code = conn.execute_command("~/cloudLinux/stream_test.sh")
            print(f"whoami: {stdout.strip()} (exit code: {exit_code})")
            
            # Test another command
            # stdout, stderr, exit_code = conn.execute_command("uname -a")
            # print(f"uname: {stdout.strip()}")
            
            # # Test simple method
            # result = conn.execute_command_simple("pwd")
            # print(f"pwd: {result.strip() if result else 'Failed'}")
            
    except SSHConnectionError as e:
        print(f"✗ Connection failed: {e}")
        return False
    
    print("✓ Connection test completed")
    return True

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
    # example  ssh 'debian@192.168.215.3' -i 