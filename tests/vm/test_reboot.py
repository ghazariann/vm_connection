#!/usr/bin/env python3
"""Manual test script for unexpected reboot detection (no pytest)."""

import logging
import time

# If your package exposes SSHConnection at the top level:
from vm_connection import SSHConnection
from vm_connection.connection import SSHConnectionError
# If you placed the error in a separate module, use this import instead:
# from vm_connection.reboot_detection import UnexpectedRebootError
# Else, if the class defines it, import from there:
from vm_connection.reboot import UnexpectedRebootError  # ← adjust if needed

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

HOST = "192.168.215.3"
USER = "debian"
KEY = "/root/.ssh/debian_vm_key"

def wait_until_disconnected(conn: SSHConnection, deadline_s: float = 30.0) -> bool:
    """Wait until the SSH connection drops (e.g., during reboot)."""
    start = time.monotonic()
    while time.monotonic() - start < deadline_s:
        if not conn.is_connected():
            return True
        time.sleep(0.8)
    return False

def main() -> bool:
    print("Testing reboot detection")
    print("=" * 40)

    conn = SSHConnection(host=HOST, user=USER, key_path=KEY)

    try:
        # 1) Initial connection and sanity check
        print("1. Initial connection...")
        conn.connect()
        print(f"   Connected: {conn.is_connected()}")
        
        
        try:
            conn.execute(
                "echo 'Step 1: starting at $(date)'; "
                "sleep 5; "
                "echo 'Step 2: still alive at $(date)'; "
                "sleep 5; "
                "echo 'Step 3: still alive at $(date)'; "
                "sleep 5; "
                "echo 'Step 4: done at $(date)'; "
                "sleep 5; "
                "echo 'Step 5: done at $(date)'",
                verbose=True,
                timeout=60,
                inactivity_timeout=10
        )
        except UnexpectedRebootError:
            print("Reboot detected during command execution!")
        
        # res = conn.execute("echo ready", verbose=False)
        # print(f"   Test command: {res.stdout.strip()}")

        # # 2) Baseline: snapshot boot identity, run a harmless command, assert no reboot
        # print("\n2. Baseline (no reboot expected):")
        # before = conn.snapshot_boot_identity()
        # res = conn.execute("echo 'no reboot path'", verbose=False)
        # print(f"   Ran harmless command: {res.stdout.strip()}")
        # try:
        #     conn.assert_same_boot(before)
        #     print("   PASS: No reboot detected (as expected).")
        # except UnexpectedRebootError as e:
        #     print(f"   FAIL: Unexpected reboot reported: {e}")
        #     return False

        # # 3) Schedule a reboot in a few seconds (non-interactive safe pattern)
        # print("\n3. Scheduling reboot on the VM (will reboot in ~3s)...")
        # # We schedule the reboot *in the future* so exec returns cleanly before the drop.
        # # - Using (sleep; systemctl reboot) avoids immediate channel kill.
        # # - nohup/background prevents the scheduler shell from being killed with the SSH session.
        # schedule_cmd = (
        #     "sudo nohup sh -c 'sleep 3; "
        #     "command -v systemctl >/dev/null 2>&1 && systemctl reboot || /sbin/reboot -f' "
        #     "</dev/null >/dev/null 2>&1 &"
        # )
        # before = conn.snapshot_boot_identity()
        # conn.execute(schedule_cmd, verbose=False)
        # print("   Reboot scheduled; waiting for disconnect...")

        # # 4) Wait until the connection drops
        # dropped = wait_until_disconnected(conn, deadline_s=30.0)
        # print(f"   Disconnected: {dropped}")
        # if not dropped:
        #     print("   FAIL: Connection did not drop; reboot may not have triggered.")
        #     return False

        # # 6) Verify reboot using boot identity comparison
        # print("\n6. Verifying reboot detection...")
        # try:
        #     conn.assert_same_boot(before)
        #     print("   FAIL: No reboot detected, but we expected one.")
        #     return False
        # except UnexpectedRebootError as e:
        #     print(f"   PASS: Reboot detected: {e}")

        # # 7) Optional: sanity command after reboot
        # res = conn.execute("echo 'post-reboot OK' && uname -r", verbose=False)
        # print(f"   Post-reboot command output:\n{res.stdout.strip()}")

        # # 8) Clean up
        # conn.disconnect()
        # print("\n8. Test completed successfully!")
        # return True

    except Exception as e:
        print(f"Error during test: {e}")
        try:
            conn.disconnect()
        except Exception:
            pass
        return False

if __name__ == "__main__":
    main()
