#!/bin/bash
# ILMA Browser Keep-Alive Daemon Init
# Ensures Chrome with profile /root/user-data/lokah2150 stays alive

SCRIPT="/root/.hermes/profiles/ilma/scripts/ilma_browser_keepalive.py"
PIDFILE="/tmp/ilma_browser_keepalive.pid"
STATUSFILE="/tmp/ilma_browser_keepalive_status.json"
PROFILE="/root/user-data/lokah2150"

mkdir -p "$PROFILE"

is_running() {
    if [ -f "$PIDFILE" ]; then
        PID=$(cat "$PIDFILE")
        if kill -0 "$PID" 2>/dev/null; then
            return 0
        fi
        rm -f "$PIDFILE"
    fi
    return 1
}

case "${1:-start}" in
    start)
        if is_running; then
            echo "ILMA Browser Keep-Alive already running (PID=$(cat $PIDFILE))"
        else
            cd /root/.hermes/profiles/ilma
            nohup python3 "$SCRIPT" --daemon > /tmp/ilma_browser_keepalive.log 2>&1 &
            sleep 2
            if is_running; then
                echo "ILMA Browser Keep-Alive started (PID=$(cat $PIDFILE))"
            else
                echo "FAILED to start ILMA Browser Keep-Alive"
                exit 1
            fi
        fi
        ;;
    stop)
        if is_running; then
            PID=$(cat "$PIDFILE")
            kill "$PID" 2>/dev/null
            sleep 1
            rm -f "$PIDFILE"
            echo "ILMA Browser Keep-Alive stopped"
        else
            echo "ILMA Browser Keep-Alive not running"
        fi
        ;;
    status)
        python3 "$SCRIPT" --status
        ;;
    restart)
        $0 stop
        sleep 2
        $0 start
        ;;
    *)
        echo "Usage: $0 {start|stop|status|restart}"
        exit 1
        ;;
esac
