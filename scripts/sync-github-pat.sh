#!/bin/bash
# Sync github.pat.json to VPS 172.16.103.253 (yapsi)
# Usage: ./sync-github-pat.sh

set -e

LOCAL_FILE="/root/credential/github.pat.json"
REMOTE_HOST="yapsi"
REMOTE_FILE="/root/credential/github.pat.json"

if [[ ! -f "$LOCAL_FILE" ]]; then
    echo "❌ Local file not found: $LOCAL_FILE"
    exit 1
fi

echo "🔄 Syncing $LOCAL_FILE → $REMOTE_HOST:$REMOTE_FILE"
scp "$LOCAL_FILE" "$REMOTE_HOST:$REMOTE_FILE"

# Verify
ssh "$REMOTE_HOST" "cat $REMOTE_FILE"
echo "✅ Sync complete"
