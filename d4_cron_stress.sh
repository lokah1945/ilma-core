#!/bin/bash
# Phase D Stress Test - runs every 5 min for 24h
cd /root/.hermes/profiles/ilma
python3 d4_stress_test.py >> /tmp/stress_test.log 2>&1
