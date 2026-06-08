#!/bin/bash

echo "==========================================="
echo "💥 FORCE-KILLING ALL DOCKER CONTAINERS"
echo "==========================================="

# 1. Kill host processes for any running container
echo "Finding PIDs of all running containers..."
RUNNING_CONTAINERS=$(docker ps -q)

if [ -n "$RUNNING_CONTAINERS" ]; then
    for container in $RUNNING_CONTAINERS; do
        name=$(docker inspect --format '{{.Name}}' $container)
        pid=$(docker inspect --format '{{.State.Pid}}' $container 2>/dev/null)
        if [ -n "$pid" ] && [ "$pid" -ne 0 ]; then
            echo "-> Killing process for $name (PID: $pid)..."
            sudo kill -9 $pid 2>/dev/null
        fi
    done
else
    echo "No running containers found."
fi

# 2. Force remove all containers
echo "Removing all containers..."
ALL_CONTAINERS=$(docker ps -aq)
if [ -n "$ALL_CONTAINERS" ]; then
    docker rm -f $ALL_CONTAINERS 2>/dev/null
else
    echo "No containers to remove."
fi

# 3. Fix AppArmor/systemd state issues
echo "Restarting AppArmor and Docker to clean up system state..."
sudo systemctl restart apparmor
sudo systemctl restart docker

# 4. Clean up any remaining dangling volumes/networks
echo "Pruning unused docker resources..."
docker system prune -f

echo "==========================================="
echo "✅ Force-kill and reset completed!"
echo "==========================================="
