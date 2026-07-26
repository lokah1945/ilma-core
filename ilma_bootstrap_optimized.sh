#!/bin/bash
# ILMA BOOTSTRAP OPTIMIZED v2.0
# Ensures the system is primed for maximum intelligence.

echo "🚀 Starting ILMA Optimized Bootstrap..."

# 1. Sync Provider Database
echo "Updating Provider Intelligence Master DB..."
python3 /root/.hermes/profiles/ilma/ilma_optimize_db.py

# 2. Verify Wiring
echo "Verifying Runtime Wiring..."
python3 /root/.hermes/profiles/ilma/ilma_runtime_wiring.py --verify

# 3. Health Check
echo "Running System Health Check..."
python3 /root/.hermes/profiles/ilma/ilma_health_check.py

echo "✅ ILMA is now primed and ready for high-intelligence operations."
