#!/usr/bin/env bash
#
# ILMA Passive Benchmark Refresh - Cron Installer
# ================================================
# Installs daily cron at 03:00 Asia/Jakarta (WIB)
# Schedule: CRON_TZ=Asia/Jakarta 0 3 * * *
#

set -e

PROFILE_DIR="/root/.hermes/profiles/ilma"
SCRIPT_NAME="ilma_passive_benchmark_refresh.py"
LOG_DIR="${PROFILE_DIR}/logs/passive_benchmark_refresh"
REPORT_DIR="${PROFILE_DIR}/docs/passive_benchmark_refresh"
BACKUP_DIR="${PROFILE_DIR}/backups/passive_benchmark_refresh"

echo "=== ILMA Passive Benchmark Refresh - Cron Installer ==="
echo ""

# Create directories
mkdir -p "${LOG_DIR}"
mkdir -p "${REPORT_DIR}"
mkdir -p "${BACKUP_DIR}"
echo "✅ Created directories"

# Detect Python path
PYTHON_PATH=$(which python3)
if [ -z "${PYTHON_PATH}" ]; then
    PYTHON_PATH="/usr/bin/python3"
fi
echo "📌 Python: ${PYTHON_PATH}"

# Detect timezone
CURRENT_TZ=$(cat /etc/timezone 2>/dev/null || date +%Z)
echo "📌 Timezone: ${CURRENT_TZ}"

# Verify script exists
SCRIPT_PATH="${PROFILE_DIR}/scripts/${SCRIPT_NAME}"
if [ ! -f "${SCRIPT_PATH}" ]; then
    echo "❌ Script not found: ${SCRIPT_PATH}"
    exit 1
fi
echo "✅ Script found: ${SCRIPT_PATH}"

# Generate cron entry
CRON_ENTRY="# ILMA Passive Benchmark Refresh - Daily 03:00 WIB
CRON_TZ=Asia/Jakarta
0 3 * * * root cd ${PROFILE_DIR} && ${PYTHON_PATH} ${SCRIPT_PATH} --run >> ${LOG_DIR}/cron.log 2>&1
"

echo ""
echo "=== CRON ENTRY ==="
echo "${CRON_ENTRY}"

# Option 1: Install via /etc/cron.d
CrontabFile="/etc/cron.d/ilma-passive-benchmark-refresh"
echo ""
read -p "Install to ${CrontabFile}? (y/N): " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "${CRON_ENTRY}" > "${CrontabFile}"
    chmod 644 "${CrontabFile}"
    echo "✅ Installed to ${CrontabFile}"
    echo ""
    echo "Contents:"
    cat "${CrontabFile}"
else
    echo "⚠️ Skipped - cron file not installed"
    echo ""
    echo "=== MANUAL INSTALL OPTIONS ==="
    echo ""
    echo "Option 1 - Add to existing crontab:"
    echo "  crontab -e"
    echo "  # Add this line:"
    echo "  ${CRON_ENTRY}"
    echo ""
    echo "Option 2 - Create cron file manually:"
    echo "  echo '${CRON_ENTRY}' > /etc/cron.d/ilma-passive-benchmark-refresh"
    echo "  chmod 644 /etc/cron.d/ilma-passive-benchmark-refresh"
    echo ""
    echo "Option 3 - Save to ILMA config for later install:"
    CONFIG_DIR="${PROFILE_DIR}/config/cron"
    mkdir -p "${CONFIG_DIR}"
    echo "${CRON_ENTRY}" > "${CONFIG_DIR}/ilma_passive_benchmark_refresh.cron"
    echo "✅ Saved to ${CONFIG_DIR}/ilma_passive_benchmark_refresh.cron"
fi

echo ""
echo "=== VERIFICATION ==="
echo "To verify cron installed, run:"
echo "  cat /etc/cron.d/ilma-passive-benchmark-refresh"
echo ""
echo "To test dry-run:"
echo "  ${PYTHON_PATH} ${SCRIPT_PATH} --dry-run"
echo ""
echo "To test validate-only:"
echo "  ${PYTHON_PATH} ${SCRIPT_PATH} --validate-only"
echo ""
echo "=== INSTALLATION STATUS ==="
if [ -f "${CrontabFile}" ]; then
    echo "Status: INSTALLED"
else
    echo "Status: PREPARED (cron file created but not installed)"
fi

exit 0