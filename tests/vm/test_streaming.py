#!/usr/bin/env python3
"""Test script for the streaming execute method."""

import sys
from vm_connection import SSHConnection

def log_output_line(line, stream_name):
    """Simple callback that prints to the console."""
    print(f"[{stream_name}] {line.strip()}")

def main():
    """Test the streaming execute functionality."""
    # if len(sys.argv) < 4:
    #     print("Usage: python test_streaming.py <host> <user> <key_path>")
    #     sys.exit(1)
    
    host = "192.168.215.3"
    user = "debian"
    key_path = "/root/.ssh/debian_vm_key"
    
    try:
        # Create connection
        conn = SSHConnection(host=host, user=user, key_path=key_path)
        
        # Connect
        print(f"Connecting to {user}@{host}...")
        conn.connect()
        print("Connected successfully!")
        
        # Test simple command with streaming
        print("\n=== Testing simple command with streaming ===")
        result = conn.execute('~/cloudLinux/stream_test.sh', 
                             output_callback=log_output_line,
                             timeout=10)
        print(f"Command completed with exit code: {result.exit_code}")
        
        # Test long-running command
        print("\n=== Testing long-running command ===")
        result = conn.execute('for i in {1..5}; do echo "Line $i"; sleep 1; done', 
                             output_callback=log_output_line,
                             timeout=30)
        print(f"Long command completed with exit code: {result.exit_code}")
        
        # Test command without callback
        print("\n=== Testing command without callback ===")
        result = conn.execute('ls -la', timeout=10, verbose=False)
        print(f"No-callback command completed with exit code: {result.exit_code}")
        print(f"Stdout: {result.stdout[:100]}..." if len(result.stdout) > 100 else f"Stdout: {result.stdout}")
        
        # Disconnect
        conn.disconnect()
        print("Disconnected.")
        
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()