#!/bin/bash
# Watch github.pat.json for changes and auto-sync to VPS
# Uses inotifywait (inotify-tools)

set -e

LOCAL_FILE="/root/credential/github.pat.json"
REMOTE_HOST="yapsi"
REMOTE_FILE="/root/credential/github.pat.json"
SCRIPT_DIR="$(dirname "$0")"
SYNC_SCRIPT="$SCRIPT_DIR/sync-github-pat.sh"

if ! command -v inotifywait &> /dev/null; then
    echo "Installing inotify-tools..."
    apt-get update && apt-get install -y inotify-tools
fi

echo "👀 Watching $LOCAL_FILE for changes..."
echo "Press Ctrl+C to stop"

# Initial sync
"$SYNC_SCRIPT"

# Watch for close_write (file written and closed), modify, move_self
inotifywait -m -e close_write,modify,move_self --format '%e %f' "$LOCAL_FILE" | while read event file; do
    echo "📝 Change detected: $event on $file"
    sleep 0.5  # debounce
    "$SYNC_SCRIPT"
done
