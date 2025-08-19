#!/usr/bin/env python3
"""Test script for the is_alive method."""

from vm_connection.connection import SSHConnection

def main():
    """Test the is_alive functionality."""
    print("Testing is_alive method")
    print("=" * 30)
    
    # Create connection
    conn = SSHConnection(
        host="192.168.215.3",
        user="debian", 
        key_path="/root/.ssh/debian_vm_key"
    )
      # Connect
    print(f"\nConnecting to {conn.user}@{conn.host}...")
    conn.connect()
                
    try:
        alive_result = conn.is_alive()
        print(f"  is_alive(): {alive_result.alive}")
        print(f"  reasons: {alive_result.reasons}")
        
        # Disconnect
        conn.disconnect()
        
        print(f"\nAfter disconnection:")
        alive_result = conn.is_alive()
        print(f"  is_alive(): {alive_result.alive}")
        print(f"  reasons: {alive_result.reasons}")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()