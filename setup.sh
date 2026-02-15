#!/bin/bash
# ============================================================
# Freedom Mobile Data Tracker — Setup Script (macOS)
# ============================================================
# This script:
#   1. Installs Python dependencies
#   2. Configures your Freedom Mobile credentials
#   3. Sets up a weekly Friday reminder notification via launchd
#   4. Adds a 'freedom' terminal alias
#   5. Creates a Dock-friendly .app for one-click launching
# ============================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TRACKER_SCRIPT="$SCRIPT_DIR/freedom_tracker.py"
REMINDER_SCRIPT="$SCRIPT_DIR/reminder_only.sh"
PLIST_NAME="com.freedom-tracker.weekly"
PLIST_PATH="$HOME/Library/LaunchAgents/$PLIST_NAME.plist"

echo "╔══════════════════════════════════════════════╗"
echo "║   📱 Freedom Mobile Data Tracker — Setup     ║"
echo "╚══════════════════════════════════════════════╝"
echo ""

# ---- Step 1: Check Python ----
echo "🔍 Checking Python installation..."
if command -v python3 &>/dev/null; then
    PYTHON=$(command -v python3)
    echo "   ✓ Found Python at: $PYTHON"
    echo "   ✓ Version: $($PYTHON --version)"
else
    echo "   ❌ Python 3 not found. Install it from https://python.org"
    exit 1
fi

# ---- Step 2: Create virtual environment & install dependencies ----
echo ""
VENV_DIR="$SCRIPT_DIR/venv"
if [ ! -d "$VENV_DIR" ]; then
    echo "🐍 Creating virtual environment..."
    $PYTHON -m venv "$VENV_DIR"
    echo "   ✓ Virtual environment created at $VENV_DIR"
else
    echo "🐍 Virtual environment already exists."
fi

# Use the venv Python from now on
PYTHON="$VENV_DIR/bin/python3"

echo "📦 Installing Python dependencies..."
"$VENV_DIR/bin/pip" install --quiet selenium webdriver-manager
echo "   ✓ selenium installed"
echo "   ✓ webdriver-manager installed"

# ---- Step 3: Check Chrome ----
echo ""
echo "🌐 Checking for Google Chrome..."
if [ -d "/Applications/Google Chrome.app" ]; then
    echo "   ✓ Google Chrome found"
else
    echo "   ⚠️  Google Chrome not found in /Applications."
    echo "   The scraper needs Chrome. Install it from https://google.com/chrome"
fi

# ---- Step 4: Configure credentials ----
echo ""
echo "🔑 Setting up your Freedom Mobile credentials..."
$PYTHON "$TRACKER_SCRIPT" --config

# ---- Step 5: Test scrape ----
echo ""
read -p "🧪 Run a test scrape now? (y/n): " TEST_SCRAPE
if [[ "$TEST_SCRAPE" == "y" || "$TEST_SCRAPE" == "Y" ]]; then
    echo ""
    $PYTHON "$TRACKER_SCRIPT" --notify
fi

# ---- Step 6: Set up weekly Friday REMINDER via launchd ----
echo ""
echo "📅 Setting up weekly Friday reminder notification..."
mkdir -p "$HOME/.freedom-tracker"

cat > "$PLIST_PATH" <<PLISTEOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>$PLIST_NAME</string>

    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>$REMINDER_SCRIPT</string>
    </array>

    <!-- Run every Friday at 6:00 PM -->
    <key>StartCalendarInterval</key>
    <dict>
        <key>Weekday</key>
        <integer>5</integer>
        <key>Hour</key>
        <integer>18</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>

    <key>StandardOutPath</key>
    <string>/Users/$USER/.freedom-tracker/launchd_stdout.log</string>

    <key>StandardErrorPath</key>
    <string>/Users/$USER/.freedom-tracker/launchd_stderr.log</string>
</dict>
</plist>
PLISTEOF

# Load the job
launchctl unload "$PLIST_PATH" 2>/dev/null || true
launchctl load "$PLIST_PATH"

echo "   ✓ Reminder scheduled: Every Friday at 6:00 PM"
echo "   ✓ Plist saved to: $PLIST_PATH"

# ---- Step 7: Add terminal alias ----
echo ""
echo "⌨️  Setting up 'freedom' terminal alias..."
ALIAS_LINE="alias freedom='$PYTHON $TRACKER_SCRIPT --notify'"

# Detect shell config file
if [ -f "$HOME/.zshrc" ]; then
    SHELL_RC="$HOME/.zshrc"
elif [ -f "$HOME/.bashrc" ]; then
    SHELL_RC="$HOME/.bashrc"
else
    SHELL_RC="$HOME/.zshrc"
fi

# Add alias if not already present
if grep -q "alias freedom=" "$SHELL_RC" 2>/dev/null; then
    echo "   ✓ Alias already exists in $SHELL_RC"
else
    echo "" >> "$SHELL_RC"
    echo "# Freedom Mobile Data Tracker" >> "$SHELL_RC"
    echo "$ALIAS_LINE" >> "$SHELL_RC"
    echo "   ✓ Added 'freedom' alias to $SHELL_RC"
fi
echo "   Run 'source $SHELL_RC' or open a new terminal to use it"

# ---- Step 8: Dock app ----
echo ""
echo "🖥️  Setting up Dock app..."
APP_DIR="$SCRIPT_DIR/Freedom Tracker.app"
if [ -d "$APP_DIR" ]; then
    echo "   ✓ Freedom Tracker.app is ready"
    echo "   Drag it to your Dock from: $SCRIPT_DIR"
else
    echo "   ⚠️  Freedom Tracker.app not found — it should be in the project folder"
fi

# ---- Done ----
echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║   ✅ Setup Complete!                                 ║"
echo "╠══════════════════════════════════════════════════════╣"
echo "║                                                      ║"
echo "║   3 ways to check your data:                         ║"
echo "║                                                      ║"
echo "║   1. 🖥️  Double-click Freedom Tracker.app (or Dock)  ║"
echo "║   2. ⌨️  Type 'freedom' in Terminal                   ║"
echo "║   3. 📅 Friday 6 PM reminder — then use #1 or #2    ║"
echo "║                                                      ║"
echo "║   Other commands:                                    ║"
echo "║   • freedom                        run + notify      ║"
echo "║   • python freedom_tracker.py --history   view past  ║"
echo "║   • python freedom_tracker.py --config    reconfigure║"
echo "║                                                      ║"
echo "╚══════════════════════════════════════════════════════╝"
