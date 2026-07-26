#!/usr/bin/env python3
"""
ILMA Monitoring Scripts
======================
System and application monitoring.
"""

SCRIPTS = [
    ("ilma_system_monitor.py", "System resource monitoring"),
    ("ilma_process_monitor.py", "Process monitoring"),
    ("ilma_network_monitor.py", "Network monitoring"),
    ("ilma_disk_monitor.py", "Disk usage monitoring"),
    ("ilma_memory_monitor.py", "Memory leak detection"),
    ("ilma_log_aggregator.py", "Log aggregation"),
    ("ilma_alerting.py", "Alert management"),
    ("ilma_metrics_collector.py", "Metrics collection"),
]

def main():
    print(f"Monitoring Scripts: {len(SCRIPTS)}")

if __name__ == "__main__":
    main()