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
        result = conn.execute("ls -la")
        print(f"Exit code: {result.exit_code}")
        print(f"Stdout: {result.stdout}")
        if result.stderr:
            print(f"Stderr: {result.stderr}")
    
    print("Connection closed automatically")


if __name__ == "__main__":
    main()
