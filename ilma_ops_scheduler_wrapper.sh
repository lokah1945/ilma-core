#!/bin/bash
# ILMA Ops Scheduler Wrapper
# Safely executes operational python scripts with logging and locks.

LOCKFILE="/tmp/ilma_scheduler.lock"
LOGFILE="/root/.hermes/profiles/ilma/logs/ops_scheduler.log"

if [ -e "${LOCKFILE}" ] && kill -0 `cat ${LOCKFILE}` 2>/dev/null; then
    echo "$(date) - Scheduler already running. Exiting." >> "${LOGFILE}"
    exit 1
fi

echo $$ > "${LOCKFILE}"

echo "======================================" >> "${LOGFILE}"
echo "Running Scheduled Ops at $(date)" >> "${LOGFILE}"

# 1. Stale Approval Scan
echo "-> Expiring stale approvals" >> "${LOGFILE}"
/usr/bin/python3 /root/.hermes/profiles/ilma/ilma_approval_queue.py expire-stale >> "${LOGFILE}" 2>&1

# 2. Drift Detection
echo "-> Running capability drift detector" >> "${LOGFILE}"
/usr/bin/python3 /root/.hermes/profiles/ilma/ilma_capability_drift_detector.py >> "${LOGFILE}" 2>&1

# 3. Log Maintenance (Run once a day, assumed if hour is 02:xx)
HR=$(date +%H)
if [ "$HR" == "02" ]; then
    echo "-> Running log maintenance" >> "${LOGFILE}"
    /usr/bin/python3 /root/.hermes/profiles/ilma/ilma_log_maintenance.py >> "${LOGFILE}" 2>&1
fi

echo "Scheduler run complete." >> "${LOGFILE}"
rm -f "${LOCKFILE}"
