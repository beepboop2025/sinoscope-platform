#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
PLIST_NAME="com.dragonscope.server"
PLIST_PATH="$HOME/Library/LaunchAgents/$PLIST_NAME.plist"

# Find node and pm2
NODE_PATH=$(which node 2>/dev/null || echo "")
PM2_PATH=$(which pm2 2>/dev/null || echo "")

if [ -z "$NODE_PATH" ]; then
  echo "Error: node not found in PATH"
  echo "Make sure Node.js is installed and in your PATH"
  exit 1
fi

if [ -z "$PM2_PATH" ]; then
  echo "pm2 not found. Installing globally..."
  npm install -g pm2
  PM2_PATH=$(which pm2)
fi

# Ensure LaunchAgents directory exists
mkdir -p "$HOME/Library/LaunchAgents"

# Unload existing agent if present
if launchctl list "$PLIST_NAME" &>/dev/null; then
  echo "Unloading existing LaunchAgent..."
  launchctl unload "$PLIST_PATH" 2>/dev/null || true
fi

# Get the PATH that includes node (handles nvm/homebrew)
NODE_DIR=$(dirname "$NODE_PATH")
CURRENT_PATH="$NODE_DIR:/usr/local/bin:/usr/bin:/bin"

cat > "$PLIST_PATH" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>$PLIST_NAME</string>
    <key>ProgramArguments</key>
    <array>
        <string>$PM2_PATH</string>
        <string>start</string>
        <string>$PROJECT_DIR/server/ecosystem.config.cjs</string>
    </array>
    <key>WorkingDirectory</key>
    <string>$PROJECT_DIR/server</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>$CURRENT_PATH</string>
        <key>HOME</key>
        <string>$HOME</string>
    </dict>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <false/>
    <key>StandardOutPath</key>
    <string>$PROJECT_DIR/server/logs/launchagent-out.log</string>
    <key>StandardErrorPath</key>
    <string>$PROJECT_DIR/server/logs/launchagent-err.log</string>
</dict>
</plist>
EOF

# Ensure log directory exists
mkdir -p "$PROJECT_DIR/server/logs"

# Load the agent
launchctl load "$PLIST_PATH"

echo ""
echo "DragonScope LaunchAgent installed successfully!"
echo "  Plist: $PLIST_PATH"
echo "  The API server will start automatically on login."
echo ""
echo "To check status: pm2 status"
echo "To uninstall:    npm run service:uninstall"
