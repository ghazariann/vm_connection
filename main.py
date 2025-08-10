"""Example usage of vm_connection package."""

from vm_connection import SSHConnection


def main():
    """Demonstrate basic SSHConnection usage."""
    print("VM Connection Example")
    
    # Create connection instance
    conn = SSHConnection(
        host="192.168.1.10",
        user="testuser", 
        key_path="/path/to/id_rsa"
    )
    
    # Example using context manager
    print("Using context manager:")
    with conn:
        if conn.is_connected():
            result = conn.execute_command("ls -la")
            print(f"Command result: {result}")
    
    print("Connection closed automatically")


if __name__ == "__main__":
    main()
