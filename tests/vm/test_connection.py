#!/usr/bin/env python3
"""Test script for vm_connection library."""

from vm_connection import SSHConnection
from vm_connection.connection import SSHConnectionError

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
            result = conn.execute("~/cloudLinux/stream_test.sh")
            print(f"Script output (exit code: {result.exit_code})")
            if result.stdout:
                print(f"Stdout: {result.stdout.strip()}")
            if result.stderr:
                print(f"Stderr: {result.stderr.strip()}")
            
            # Test another command
            result = conn.execute("uname -a")
            print(f"uname: {result.stdout.strip()}")
            
            # Test simple command
            result = conn.execute("pwd", verbose=False)
            print(f"pwd: {result.stdout.strip() if result.stdout else 'Failed'}")
            
    except SSHConnectionError as e:
        print(f"✗ Connection failed: {e}")
        return False
    
    print("✓ Connection test completed")
    return True

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
    # example  ssh 'debian@192.168.215.3' -i 