  # vm_connection 
  A Python module for SSH connection management to remote Linux VMs with resilient command execution, real-time streaming, and reboot detection.
   ### Install Dependencies

  Using pip:
  ```bash
  pip install -r requirements.txt
  ```

  Using uv (recommended):
  ```bash
  uv pip install -r requirements.txt
  ```

  ## Running Tests

  Run the complete test suite:
  ```bash
  pytest
  ```

## Design Choices

### `is_alive()` Method

The `is_alive()` method uses a **layered approach** to check the VM’s operational state by testing different network layers:

1. **Application Layer: SSH**
   - First, we check if SSH is active. If SSH works, the VM is considered **operational**, as SSH confirms both the OS and SSH service are running.

2. **Transport Layer: TCP (Ports 22, 443, 80)**
   - If SSH fails, we check common TCP ports (e.g., SSH, HTTP, HTTPS). If any port responds (even with a refused connection), it confirms the VM’s **network stack** is working.

3. **IP Layer: ICMP (Ping)**
   - If both SSH and TCP fail, we ping the VM to verify if it’s reachable at the **network level**. A successful ping indicates the VM's **IP stack** is alive.  
   - **Note**: There is a risk of firewalls blocking ICMP, which could prevent a successful ping even if the VM is operational.

- This approach is designed under the assumption that there is **no out-of-band access** (e.g., serial or console access). All checks rely on network-based communication to determine if the VM is alive.
- By testing different layers (SSH, TCP, and ICMP), we ensure a more **comprehensive check**, minimizing the risk of false positives or negatives.
- The VM is considered **operational** if any of the checks show the system is alive; otherwise, it’s marked as **non-operational**.

### Reboot Guard Decorator with Boot Identity Snapshot

The `resilient` decorator ensures methods are protected against unexpected system reboots by comparing boot identities before and after execution:

1. **Snapshot Before Execution**:
   - Captures the system’s boot identity by reading the **/proc/sys/kernel/random/boot_id** file.

2. **Reconnection Handling**:
   - If the connection fails, the decorator attempts to reconnect and checks the boot identity again after reconnecting.

3. **Snapshot After Execution**:
   - Compares the boot identity after the method execution. If the identity changes, it indicates a reboot.

### Handling Long-Running, Network-Disrupting Commands

1. **`execute_long` Method**: 
   - Uses `nohup` to run the command in the background, ensuring it continues running even after SSH disconnection.
   - Streams the output of the command and exit code to a temporary file on the remote machine.

2. **Log Streaming**:
   - Regularly polls the log file for new content, ensuring continuous output streaming until the command completes or times out.

3. **Reconnection Logic**:
   - The `@resilient` decorator handles SSH disconnections and attempts reconnection.
   - After reconnection, continues to stream the log file or reads results from the log and exit code files if the exit code is 1, without re-running the task.

### Testing Strategy

1. **Mocking External Dependencies**:
   - `paramiko.SSHClient`, `paramiko.Transport`, and `paramiko.Channel` are mocked to simulate SSH connections and channel behaviors without requiring a live VM.
   - The simulated responses from these mocked components mimic the output of a remote machine, ensuring accurate testing of command execution and handling of various output scenarios.

2. **Test Scenarios**:
   - **Connection Handling**: Tests cover scenarios such as successful connections or various SSH connection failures (e.g., authentication issues, unreachable hosts).
   - **Command Execution**: Tests validate the execution of commands via mocked channels, ensuring correct handling of stdout, stderr, and exit codes.
   - **Reconnection Logic**: The strategy simulates network drops and verifies that the connection is re-established successfully after a disconnection.

This strategy is appropriate as it ensures the module's resilience and correctness without relying on a live environment, making tests fast and reliable.

Additionally, in the `tests/vm` folder, real virtual machine testing was conducted during the initial stage to validate the module's functionality in a live environment. This portion of the tests are for reference only.