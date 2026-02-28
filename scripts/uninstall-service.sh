#!/usr/bin/env bash
set -euo pipefail

PLIST_NAME="com.dragonscope.server"
PLIST_PATH="$HOME/Library/LaunchAgents/$PLIST_NAME.plist"

echo "Uninstalling DragonScope LaunchAgent..."

# Unload the agent
if [ -f "$PLIST_PATH" ]; then
  launchctl unload "$PLIST_PATH" 2>/dev/null || true
  rm -f "$PLIST_PATH"
  echo "  LaunchAgent removed."
else
  echo "  LaunchAgent not found (already removed)."
fi

# Stop pm2 processes
if command -v pm2 &>/dev/null; then
  pm2 stop dragonscope-collector 2>/dev/null || true
  pm2 stop dragonscope-dataserver 2>/dev/null || true
  pm2 delete dragonscope-collector 2>/dev/null || true
  pm2 delete dragonscope-dataserver 2>/dev/null || true
  echo "  PM2 processes stopped and removed."
else
  echo "  pm2 not found, skipping process cleanup."
fi

echo ""
echo "DragonScope service uninstalled."
