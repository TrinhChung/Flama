#!/usr/bin/env bash
# ==============================================================================
# Flama - Launch Chrome with Isolated Profile & Remote Debugging
# ==============================================================================
# Golden Rule: Never use the user's default/personal profile for DevTools/MCP.
# ==============================================================================

set -euo pipefail

PORT="${1:-9222}"
URL="${2:-http://localhost:5173}"
PROFILE_DIR="${3:-$HOME/.gemini/chrome-profiles/flama-devtools}"

echo "============================================================"
echo "🚀 Flama Chrome DevTools Launcher (Isolated Profile)"
echo "============================================================"

# Detect Chrome binary based on OS
CHROME_BIN=""
if [[ "$OSTYPE" == "darwin"* ]]; then
  CHROME_BIN="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
  if command -v google-chrome &>/dev/null; then
    CHROME_BIN="google-chrome"
  elif command -v google-chrome-stable &>/dev/null; then
    CHROME_BIN="google-chrome-stable"
  elif command -v chromium &>/dev/null; then
    CHROME_BIN="chromium"
  fi
elif [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" || "$OSTYPE" == "win32" ]]; then
  CHROME_BIN="/c/Program Files/Google/Chrome/Application/chrome.exe"
fi

if [[ -z "$CHROME_BIN" ]]; then
  echo "❌ Google Chrome executable not found."
  exit 1
fi

mkdir -p "$PROFILE_DIR"

echo " Chrome Executable : $CHROME_BIN"
echo " Isolated Profile  : $PROFILE_DIR"
echo " Debug Port        : $PORT"
echo " Target URL        : $URL"
echo "------------------------------------------------------------"

"$CHROME_BIN" \
  --remote-debugging-port="$PORT" \
  --user-data-dir="$PROFILE_DIR" \
  --no-first-run \
  --no-default-browser-check \
  "$URL" &

echo "✅ Chrome launched in background with isolated profile."
echo "💡 Chrome DevTools MCP can attach to port $PORT."
echo "============================================================"
