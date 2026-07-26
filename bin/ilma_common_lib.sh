#!/bin/bash
# ILMA Common Diagnostic Library
# Shared by ilma_bootstrap.sh and ilma_system_status.sh
# Generated: 2026-05-24 17:46:58

# ── Common functions ────────────────────────────────────────────

check_pid() {
    local pid_file="$1"
    if [ -f "$pid_file" ]; then
        local pid=$(cat "$pid_file" 2>/dev/null)
        if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
            echo "RUNNING (PID: $pid)"
        else
            echo "DEAD/FILE-ONLY"
        fi
    else
        echo "NOT_FOUND"
    fi
}

check_telegram() {
    local state_file="$BASE/gateway_state.json"
    if [ -f "$state_file" ]; then
        grep -q '"telegram".*"connected"' "$state_file" 2>/dev/null && echo "CONNECTED" || echo "DISCONNECTED"
    else
        echo "UNKNOWN"
    fi
}

check_load() {
    awk '{printf "%.2f", $1}' /proc/loadavg 2>/dev/null || echo "N/A"
}

check_memory() {
    free -m | awk '/Mem:/ {printf "%dMi / %dMi", $3, $2}' 2>/dev/null || echo "N/A"
}

check_disk() {
    df -h . | awk 'NR==2 {printf "%s / %s (%s used)", $3, $2, $5}' 2>/dev/null || echo "N/A"
}

check_uptime() {
    uptime -p 2>/dev/null | sed 's/up //' || echo "N/A"
}

check_scripts_count() {
    ls "$BASE/scripts"/*.py 2>/dev/null | wc -l
}

check_logs_size() {
    du -sh "$BASE/logs" 2>/dev/null | awk '{print $1}' || echo "N/A"
}

check_health() {
    local cron_lock="$BASE/cron/.tick.lock"
    if [ -f "$cron_lock" ] && [ -s "$cron_lock" ]; then
        echo "CRON_OK"
    else
        echo "CRON_EMPTY_OR_MISSING"
    fi
}

# Report header
echo_report_header() {
    echo "═══════════════════════════════════════════════════════"
    echo "  ILMA System Status Report"
    echo "  Generated: $(date '+%Y-%m-%d %H:%M:%S')"
    echo "═══════════════════════════════════════════════════════"
}
