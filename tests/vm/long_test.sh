#!/bin/bash

# Function to simulate normal operations
normal_operation() {
    for i in {1..2}; do
        echo "Step $i: Normal operation at $(date)"
        sleep 2
    done
}

# Function to simulate network disruption (forcefully disconnect SSH)
network_disruption() {
    echo "Simulating network disruption by killing SSH session at $(date)"
    
    # Get the PID of the current SSH session (this will terminate it)
    SSH_PID=$(ps -o pid= -C sshd --ppid $$)
    
    if [ -n "$SSH_PID" ]; then
        echo "Killing SSH process with PID: $SSH_PID"
        sudo kill -9 $SSH_PID  # Forcefully terminate the SSH session
    else
        echo "No SSH session found."
    fi
    
   
}

# Function to simulate post-disruption operations
post_disruption() {
    for i in {3..5}; do
        echo "Step $i: Post-disruption operation at $(date)"
        sleep 2
    done
}

# Run normal operations (Steps 1 and 2)
normal_operation

# Simulate network disruption (Step 3)
network_disruption

# Run normal operations (Steps 1 and 2)
normal_operation

 # Restart SSH service after killing SSH session
echo "Restarting SSH service to allow new connections"
sudo systemctl start sshd  # Restart SSH daemon

# Run post-disruption operations (Steps 4 and 5)
post_disruption

echo "Network disruption test completed at $(date)"
