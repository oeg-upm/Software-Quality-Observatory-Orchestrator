#!/usr/bin/env bash

set -euo pipefail

echo "========================================"
echo "SQOO maintenance - $(date -Iseconds)"
echo "========================================"

echo "[INFO] Disk usage before cleanup:"
df -h /

echo "[INFO] Removing dangling Docker images..."
docker image prune -f --filter "until=168h"

echo "[INFO] Removing unused build cache..."
docker builder prune -a -f --filter "until=168h"

echo "[INFO] Disk usage after cleanup:"
df -h /

echo "[INFO] Docker storage usage:"
docker system df

DISK_USAGE=$(df -P / | awk 'NR==2 {gsub(/%/, "", $5); print $5}')

if [ "$DISK_USAGE" -ge 85 ]; then
    echo "[WARNING] Disk usage is above the recommended threshold: ${DISK_USAGE}%"
fi

echo "[INFO] Maintenance completed."