#!/bin/bash
# ILMA Browser Keep-Alive Watchdog
# Runs every 5 minutes to ensure daemon is alive
# If daemon dies, restart it

SCRIPT="/root/.hermes/profiles/ilma/scripts/ilma_browser_keepalive.py"
PIDFILE="/tmp/ilma_browser_keepalive.pid"
STATUSFILE="/tmp/ilma_browser_keepalive_status.json"
LOG="/tmp/ilma_browser_keepalive_watchdog.log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG"
}

is_alive() {
    if [ -f "$PIDFILE" ]; then
        PID=$(cat "$PIDFILE" 2>/dev/null)
        if [ -n "$PID" ] && kill -0 "$PID" 2>/dev/null; then
            return 0
        fi
    fi
    return 1
}

if is_alive; then
    log "OK — daemon alive (PID=$(cat $PIDFILE))"
else
    log "WARN — daemon dead, restarting..."
    cd /root/.hermes/profiles/ilma
    python3 "$SCRIPT" --daemon > /tmp/ilma_browser_keepalive.log 2>&1 &
    sleep 3
    if is_alive; then
        log "OK — daemon restarted (PID=$(cat $PIDFILE))"
    else
        log "ERROR — restart failed"
    fi
fi
