#!/usr/bin/env python3
"""
ILMA System Administration Engine
=================================
Server monitoring, process management, and automation capabilities.

Classes: ServerMonitor, ProcessManager, AutomationRunner

Usage:
    python3 ilma_sysadmin_engine.py --server-stats
    python3 ilma_sysadmin_engine.py --process-list
    python3 ilma_sysadmin_engine.py --run-automation --file /path/to/script.py

Author: ILMA v5.0
Version: 1.0.0
"""

from __future__ import annotations

import argparse
import datetime
import json
import logging
import os
import psutil
import re
import signal
import socket
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("SysAdminEngine")


# =============================================================================
# ENUMS AND DATA STRUCTURES
# =============================================================================

class ProcessStatus(Enum):
    """Process status values."""
    RUNNING = "running"
    SLEEPING = "sleeping"
    STOPPED = "stopped"
    ZOMBIE = "zombie"
    UNKNOWN = "unknown"


@dataclass
class ServerMetrics:
    """Server performance metrics."""
    timestamp: datetime
    cpu_percent: float
    memory_percent: float
    memory_used_gb: float
    memory_total_gb: float
    disk_percent: float
    disk_used_gb: float
    disk_total_gb: float
    load_average: tuple
    network_sent_mb: float
    network_recv_mb: float
    uptime_seconds: int


@dataclass
class ProcessInfo:
    """Process information."""
    pid: int
    name: str
    username: str
    status: ProcessStatus
    cpu_percent: float
    memory_percent: float
    memory_mb: float
    create_time: datetime
    command: str


@dataclass
class AutomationTask:
    """Automation task definition."""
    id: str
    name: str
    script_path: str
    schedule: Optional[str] = None
    last_run: Optional[datetime] = None
    last_status: Optional[str] = None
    enabled: bool = True


# =============================================================================
# SERVER MONITOR CLASS
# =============================================================================

class ServerMonitor:
    """
    Server monitoring with real-time metrics collection.
    
    Collects CPU, memory, disk, network, and load average metrics.
    """
    
    def __init__(self, collection_interval: int = 60):
        self.collection_interval = collection_interval
        self.metrics_history: List[ServerMetrics] = []
        self.alert_thresholds = {
            "cpu_percent": 90.0,
            "memory_percent": 90.0,
            "disk_percent": 85.0
        }
        logger.info("ServerMonitor initialized")
    
    def collect_metrics(self) -> ServerMetrics:
        """Collect current server metrics."""
        try:
            # CPU metrics
            cpu_percent = psutil.cpu_percent(interval=1)
            load_avg = os.getloadavg() if hasattr(os, 'getloadavg') else (0.0, 0.0, 0.0)
            
            # Memory metrics
            mem = psutil.virtual_memory()
            memory_used_gb = mem.used / (1024 ** 3)
            memory_total_gb = mem.total / (1024 ** 3)
            memory_percent = mem.percent
            
            # Disk metrics
            disk = psutil.disk_usage('/')
            disk_used_gb = disk.used / (1024 ** 3)
            disk_total_gb = disk.total / (1024 ** 3)
            disk_percent = disk.percent
            
            # Network metrics
            net = psutil.net_io_counters()
            network_sent_mb = net.bytes_sent / (1024 ** 2)
            network_recv_mb = net.bytes_recv / (1024 ** 2)
            
            # System uptime
            boot_time = datetime.fromtimestamp(psutil.boot_time())
            uptime_seconds = int((datetime.now() - boot_time).total_seconds())
            
            metrics = ServerMetrics(
                timestamp=datetime.now(),
                cpu_percent=cpu_percent,
                memory_percent=memory_percent,
                memory_used_gb=memory_used_gb,
                memory_total_gb=memory_total_gb,
                disk_percent=disk_percent,
                disk_used_gb=disk_used_gb,
                disk_total_gb=disk_total_gb,
                load_average=load_avg,
                network_sent_mb=network_sent_mb,
                network_recv_mb=network_recv_mb,
                uptime_seconds=uptime_seconds
            )
            
            self.metrics_history.append(metrics)
            
            # Keep only last 1000 metrics
            if len(self.metrics_history) > 1000:
                self.metrics_history = self.metrics_history[-1000:]
            
            return metrics
            
        except Exception as e:
            logger.error(f"Failed to collect metrics: {e}")
            raise
    
    def get_current_stats(self) -> Dict[str, Any]:
        """Get current server statistics."""
        metrics = self.collect_metrics()
        
        return {
            "timestamp": metrics.timestamp.isoformat(),
            "cpu": {
                "percent": metrics.cpu_percent,
                "load_average": metrics.load_average
            },
            "memory": {
                "percent": metrics.memory_percent,
                "used_gb": metrics.memory_used_gb,
                "total_gb": metrics.memory_total_gb
            },
            "disk": {
                "percent": metrics.disk_percent,
                "used_gb": metrics.disk_used_gb,
                "total_gb": metrics.disk_total_gb
            },
            "network": {
                "sent_mb": metrics.network_sent_mb,
                "recv_mb": metrics.network_recv_mb
            },
            "uptime_seconds": metrics.uptime_seconds,
            "uptime_formatted": self._format_uptime(metrics.uptime_seconds)
        }
    
    def check_alerts(self) -> List[Dict[str, Any]]:
        """Check for alert conditions."""
        metrics = self.collect_metrics()
        alerts = []
        
        if metrics.cpu_percent > self.alert_thresholds["cpu_percent"]:
            alerts.append({
                "type": "cpu",
                "severity": "high",
                "message": f"CPU usage at {metrics.cpu_percent:.1f}%",
                "value": metrics.cpu_percent,
                "threshold": self.alert_thresholds["cpu_percent"]
            })
        
        if metrics.memory_percent > self.alert_thresholds["memory_percent"]:
            alerts.append({
                "type": "memory",
                "severity": "high",
                "message": f"Memory usage at {metrics.memory_percent:.1f}%",
                "value": metrics.memory_percent,
                "threshold": self.alert_thresholds["memory_percent"]
            })
        
        if metrics.disk_percent > self.alert_thresholds["disk_percent"]:
            alerts.append({
                "type": "disk",
                "severity": "high",
                "message": f"Disk usage at {metrics.disk_percent:.1f}%",
                "value": metrics.disk_percent,
                "threshold": self.alert_thresholds["disk_percent"]
            })
        
        return alerts
    
    def get_system_info(self) -> Dict[str, Any]:
        """Get comprehensive system information."""
        try:
            info = {
                "hostname": socket.gethostname(),
                "platform": sys.platform,
                "python_version": sys.version,
                "cpu_count": psutil.cpu_count(logical=False),
                "cpu_count_logical": psutil.cpu_count(logical=True),
                "boot_time": datetime.fromtimestamp(psutil.boot_time()).isoformat(),
                "process_count": len(psutil.pids())
            }
            
            # Get disk partitions
            partitions = []
            for part in psutil.disk_partitions():
                try:
                    usage = psutil.disk_usage(part.mountpoint)
                    partitions.append({
                        "device": part.device,
                        "mountpoint": part.mountpoint,
                        "fstype": part.fstype,
                        "total_gb": usage.total / (1024 ** 3),
                        "used_gb": usage.used / (1024 ** 3),
                        "percent": usage.percent
                    })
                except PermissionError:
                    continue
            
            info["partitions"] = partitions
            
            return info
            
        except Exception as e:
            logger.error(f"Failed to get system info: {e}")
            return {}
    
    def get_metrics_history(self, limit: int = 60) -> List[Dict[str, Any]]:
        """Get historical metrics."""
        history = self.metrics_history[-limit:]
        
        return [
            {
                "timestamp": m.timestamp.isoformat(),
                "cpu_percent": m.cpu_percent,
                "memory_percent": m.memory_percent,
                "disk_percent": m.disk_percent
            }
            for m in history
        ]
    
    def _format_uptime(self, seconds: int) -> str:
        """Format uptime in human-readable format."""
        days = seconds // 86400
        hours = (seconds % 86400) // 3600
        minutes = (seconds % 3600) // 60
        
        parts = []
        if days > 0:
            parts.append(f"{days}d")
        if hours > 0:
            parts.append(f"{hours}h")
        if minutes > 0 or not parts:
            parts.append(f"{minutes}m")
        
        return " ".join(parts)
    
    def set_alert_threshold(self, metric: str, value: float) -> bool:
        """Set alert threshold for a metric."""
        if metric in self.alert_thresholds:
            self.alert_thresholds[metric] = value
            logger.info(f"Alert threshold for {metric} set to {value}")
            return True
        return False


# =============================================================================
# PROCESS MANAGER CLASS
# =============================================================================

class ProcessManager:
    """
    Process management with monitoring and control capabilities.
    
    Supports listing, killing, prioritizing, and monitoring processes.
    """
    
    def __init__(self):
        self.process_cache: Dict[int, ProcessInfo] = {}
        self.update_cache()
        logger.info("ProcessManager initialized")
    
    def update_cache(self) -> None:
        """Update process information cache."""
        self.process_cache.clear()
        
        for proc in psutil.process_iter(['pid', 'name', 'username', 'status', 
                                          'cpu_percent', 'memory_percent', 
                                          'memory_info', 'create_time', 'cmdline']):
            try:
                pinfo = proc.info
                
                status_map = {
                    'running': ProcessStatus.RUNNING,
                    'sleeping': ProcessStatus.SLEEPING,
                    'stopped': ProcessStatus.STOPPED,
                    'zombie': ProcessStatus.ZOMBIE
                }
                
                process_info = ProcessInfo(
                    pid=pinfo['pid'],
                    name=pinfo['name'],
                    username=pinfo['username'],
                    status=status_map.get(pinfo['status'], ProcessStatus.UNKNOWN),
                    cpu_percent=pinfo['cpu_percent'] or 0.0,
                    memory_percent=pinfo['memory_percent'] or 0.0,
                    memory_mb=(pinfo['memory_info'].rss / (1024 * 1024)) if pinfo['memory_info'] else 0,
                    create_time=datetime.fromtimestamp(pinfo['create_time']),
                    command=" ".join(pinfo['cmdline']) if pinfo['cmdline'] else pinfo['name']
                )
                
                self.process_cache[proc.pid] = process_info
                
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
    
    def list_processes(
        self,
        sort_by: str = "cpu",
        reverse: bool = True,
        limit: Optional[int] = None,
        filter_name: Optional[str] = None
    ) -> List[ProcessInfo]:
        """List processes with optional filtering and sorting."""
        self.update_cache()
        
        processes = list(self.process_cache.values())
        
        # Filter by name
        if filter_name:
            processes = [p for p in processes if filter_name.lower() in p.name.lower()]
        
        # Sort
        if sort_by == "cpu":
            processes.sort(key=lambda p: p.cpu_percent, reverse=reverse)
        elif sort_by == "memory":
            processes.sort(key=lambda p: p.memory_mb, reverse=reverse)
        elif sort_by == "pid":
            processes.sort(key=lambda p: p.pid, reverse=reverse)
        elif sort_by == "name":
            processes.sort(key=lambda p: p.name.lower(), reverse=reverse)
        
        # Limit
        if limit:
            processes = processes[:limit]
        
        return processes
    
    def get_process_by_pid(self, pid: int) -> Optional[ProcessInfo]:
        """Get process information by PID."""
        try:
            proc = psutil.Process(pid)
            pinfo = proc.info
            
            status_map = {
                'running': ProcessStatus.RUNNING,
                'sleeping': ProcessStatus.SLEEPING,
                'stopped': ProcessStatus.STOPPED,
                'zombie': ProcessStatus.ZOMBIE
            }
            
            return ProcessInfo(
                pid=pinfo['pid'],
                name=pinfo['name'],
                username=pinfo['username'],
                status=status_map.get(pinfo['status'], ProcessStatus.UNKNOWN),
                cpu_percent=pinfo['cpu_percent'] or 0.0,
                memory_percent=pinfo['memory_percent'] or 0.0,
                memory_mb=(pinfo['memory_info'].rss / (1024 * 1024)) if pinfo['memory_info'] else 0,
                create_time=datetime.fromtimestamp(pinfo['create_time']),
                command=" ".join(pinfo['cmdline']) if pinfo['cmdline'] else pinfo['name']
            )
            
        except psutil.NoSuchProcess:
            return None
        except Exception as e:
            logger.error(f"Failed to get process {pid}: {e}")
            return None
    
    def kill_process(self, pid: int, force: bool = False) -> bool:
        """Kill a process by PID."""
        try:
            proc = psutil.Process(pid)
            
            if force:
                proc.kill()
            else:
                proc.terminate()
            
            # Wait for process to terminate
            try:
                proc.wait(timeout=5)
            except psutil.TimeoutExpired:
                # Force kill if terminate didn't work
                proc.kill()
            
            logger.info(f"Process {pid} terminated")
            return True
            
        except psutil.NoSuchProcess:
            logger.warning(f"Process {pid} not found")
            return False
        except psutil.AccessDenied:
            logger.error(f"Access denied to kill process {pid}")
            return False
        except Exception as e:
            logger.error(f"Failed to kill process {pid}: {e}")
            return False
    
    def kill_by_name(self, name: str, include_children: bool = True) -> int:
        """Kill all processes matching a name."""
        killed = 0
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                if proc.name() == name:
                    if self.kill_process(proc.pid(), force=True):
                        killed += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        
        logger.info(f"Killed {killed} processes matching '{name}'")
        return killed
    
    def set_process_priority(self, pid: int, priority: int) -> bool:
        """Set process priority (lower is higher priority on Unix)."""
        try:
            proc = psutil.Process(pid)
            proc.nice(priority)
            logger.info(f"Set process {pid} priority to {priority}")
            return True
        except Exception as e:
            logger.error(f"Failed to set priority for {pid}: {e}")
            return False
    
    def get_process_tree(self, pid: int) -> Dict[str, Any]:
        """Get process tree for a given PID."""
        try:
            proc = psutil.Process(pid)
            
            tree = {
                "pid": proc.pid,
                "name": proc.name(),
                "children": []
            }
            
            children = proc.children(recursive=True)
            for child in children:
                tree["children"].append({
                    "pid": child.pid,
                    "name": child.name(),
                    "status": str(child.status())
                })
            
            return tree
            
        except psutil.NoSuchProcess:
            return {}
        except Exception as e:
            logger.error(f"Failed to get process tree for {pid}: {e}")
            return {}
    
    def get_resource_intensive_processes(self, top_n: int = 10) -> List[ProcessInfo]:
        """Get top N resource-intensive processes."""
        return self.list_processes(sort_by="cpu", limit=top_n)
    
    def search_processes(self, pattern: str) -> List[ProcessInfo]:
        """Search for processes matching a pattern in command line."""
        self.update_cache()
        
        regex = re.compile(pattern, re.IGNORECASE)
        matches = []
        
        for proc in self.process_cache.values():
            if regex.search(proc.command):
                matches.append(proc)
        
        return matches


# =============================================================================
# AUTOMATION RUNNER CLASS
# =============================================================================

class AutomationRunner:
    """
    Task automation runner with scheduling and logging.
    
    Manages automated tasks, maintains execution history, and provides
    failure recovery capabilities.
    """
    
    def __init__(self, tasks_dir: str = "/tmp/ilma_automation"):
        self.tasks_dir = Path(tasks_dir)
        self.tasks_dir.mkdir(parents=True, exist_ok=True)
        self.tasks_file = self.tasks_dir / "tasks.json"
        self.logs_dir = self.tasks_dir / "logs"
        self.logs_dir.mkdir(exist_ok=True)
        self.tasks: List[AutomationTask] = []
        self.load_tasks()
        logger.info("AutomationRunner initialized")
    
    def load_tasks(self) -> None:
        """Load tasks from file."""
        if self.tasks_file.exists():
            try:
                with open(self.tasks_file) as f:
                    data = json.load(f)
                    self.tasks = [
                        AutomationTask(
                            id=t['id'],
                            name=t['name'],
                            script_path=t['script_path'],
                            schedule=t.get('schedule'),
                            last_run=datetime.fromisoformat(t['last_run']) if t.get('last_run') else None,
                            last_status=t.get('last_status'),
                            enabled=t.get('enabled', True)
                        )
                        for t in data
                    ]
            except Exception as e:
                logger.error(f"Failed to load tasks: {e}")
    
    def save_tasks(self) -> None:
        """Save tasks to file."""
        try:
            with open(self.tasks_file, "w") as f:
                json.dump([
                    {
                        "id": t.id,
                        "name": t.name,
                        "script_path": t.script_path,
                        "schedule": t.schedule,
                        "last_run": t.last_run.isoformat() if t.last_run else None,
                        "last_status": t.last_status,
                        "enabled": t.enabled
                    }
                    for t in self.tasks
                ], f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save tasks: {e}")
    
    def add_task(self, name: str, script_path: str, schedule: Optional[str] = None) -> str:
        """Add a new automation task."""
        task_id = f"task_{len(self.tasks) + 1:03d}"
        
        task = AutomationTask(
            id=task_id,
            name=name,
            script_path=script_path,
            schedule=schedule
        )
        
        self.tasks.append(task)
        self.save_tasks()
        
        logger.info(f"Added task: {task_id} - {name}")
        return task_id
    
    def remove_task(self, task_id: str) -> bool:
        """Remove a task by ID."""
        original_count = len(self.tasks)
        self.tasks = [t for t in self.tasks if t.id != task_id]
        
        if len(self.tasks) < original_count:
            self.save_tasks()
            logger.info(f"Removed task: {task_id}")
            return True
        
        return False
    
    def run_task(self, task_id: str) -> Dict[str, Any]:
        """Execute a task and return results."""
        task = next((t for t in self.tasks if t.id == task_id), None)
        
        if not task:
            return {"success": False, "error": f"Task not found: {task_id}"}
        
        # Create log file
        log_file = self.logs_dir / f"{task_id}_{int(time.time())}.log"
        
        try:
            logger.info(f"Running task: {task.name}")
            
            # Execute script
            start_time = time.time()
            
            result = subprocess.run(
                ["python3", task.script_path] if task.script_path.endswith(".py") else ["bash", task.script_path],
                capture_output=True,
                text=True,
                timeout=300
            )
            
            execution_time = time.time() - start_time
            
            # Write log
            with open(log_file, "w") as f:
                f.write(f"Task: {task.name}\n")
                f.write(f"Script: {task.script_path}\n")
                f.write(f"Start: {datetime.now().isoformat()}\n")
                f.write(f"Duration: {execution_time:.2f}s\n")
                f.write(f"Exit Code: {result.returncode}\n\n")
                f.write("=== STDOUT ===\n")
                f.write(result.stdout)
                f.write("\n=== STDERR ===\n")
                f.write(result.stderr)
            
            # Update task
            task.last_run = datetime.now()
            task.last_status = "success" if result.returncode == 0 else "failed"
            self.save_tasks()
            
            return {
                "success": result.returncode == 0,
                "task_id": task_id,
                "task_name": task.name,
                "execution_time": execution_time,
                "exit_code": result.returncode,
                "log_file": str(log_file),
                "stdout": result.stdout[:500],
                "stderr": result.stderr[:500]
            }
            
        except subprocess.TimeoutExpired:
            logger.error(f"Task {task_id} timed out")
            task.last_run = datetime.now()
            task.last_status = "timeout"
            return {"success": False, "error": "Task timed out", "log_file": str(log_file)}
            
        except Exception as e:
            logger.error(f"Task {task_id} failed: {e}")
            task.last_run = datetime.now()
            task.last_status = "error"
            return {"success": False, "error": str(e)}
    
    def list_tasks(self) -> List[Dict[str, Any]]:
        """List all tasks."""
        return [
            {
                "id": t.id,
                "name": t.name,
                "script": t.script_path,
                "schedule": t.schedule,
                "last_run": t.last_run.isoformat() if t.last_run else None,
                "last_status": t.last_status,
                "enabled": t.enabled
            }
            for t in self.tasks
        ]
    
    def get_task_logs(self, task_id: str, limit: int = 10) -> List[str]:
        """Get recent log files for a task."""
        logs = sorted(self.logs_dir.glob(f"{task_id}_*.log"), reverse=True)
        
        log_contents = []
        for log in logs[:limit]:
            try:
                with open(log) as f:
                    log_contents.append(f.read()[:2000])  # Limit each log entry
            except Exception:
                continue
        
        return log_contents
    
    def enable_task(self, task_id: str) -> bool:
        """Enable a task."""
        task = next((t for t in self.tasks if t.id == task_id), None)
        if task:
            task.enabled = True
            self.save_tasks()
            return True
        return False
    
    def disable_task(self, task_id: str) -> bool:
        """Disable a task."""
        task = next((t for t in self.tasks if t.id == task_id), None)
        if task:
            task.enabled = False
            self.save_tasks()
            return True
        return False
    
    def run_all(self, parallel: bool = False) -> List[Dict[str, Any]]:
        """Run all enabled tasks."""
        enabled_tasks = [t for t in self.tasks if t.enabled]
        
        if not enabled_tasks:
            logger.info("No enabled tasks to run")
            return []
        
        results = []
        
        if parallel:
            # Run in parallel (simplified - not truly parallel in this implementation)
            for task in enabled_tasks:
                results.append(self.run_task(task.id))
        else:
            for task in enabled_tasks:
                results.append(self.run_task(task.id))
        
        return results


# =============================================================================
# MAIN FUNCTION
# =============================================================================

def main():
    """Main entry point with CLI argument parsing."""
    parser = argparse.ArgumentParser(
        description="ILMA System Administration Engine - Server monitoring, process management, and automation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Server Monitoring
  %(prog)s --server-stats
  %(prog)s --server-info
  %(prog)s --check-alerts
  
  # Process Management
  %(prog)s --process-list
  %(prog)s --process-list --sort memory --limit 20
  %(prog)s --kill-process 1234
  %(prog)s --kill-by-name nginx
  %(prog)s --process-tree 1234
  
  # Automation
  %(prog)s --add-task --name "backup" --script /path/to/backup.py
  %(prog)s --run-task task_001
  %(prog)s --list-tasks
  %(prog)s --run-all-tasks
        """
    )
    
    parser.add_argument("--version", action="version", version="%(prog)s 1.0.0")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose output")
    
    # Server monitoring options
    parser.add_argument("--server-stats", action="store_true", help="Get current server statistics")
    parser.add_argument("--server-info", action="store_true", help="Get detailed system information")
    parser.add_argument("--check-alerts", action="store_true", help="Check for alert conditions")
    parser.add_argument("--metrics-history", action="store_true", help="Show metrics history")
    
    # Process management options
    parser.add_argument("--process-list", action="store_true", help="List running processes")
    parser.add_argument("--process-info", type=int, metavar="PID", help="Get process info")
    parser.add_argument("--kill-process", type=int, metavar="PID", help="Kill a process")
    parser.add_argument("--kill-by-name", metavar="NAME", help="Kill processes by name")
    parser.add_argument("--process-tree", type=int, metavar="PID", help="Get process tree")
    parser.add_argument("--sort", choices=["cpu", "memory", "pid", "name"], default="cpu", help="Sort processes by")
    parser.add_argument("--limit", type=int, help="Limit number of processes shown")
    
    # Automation options
    parser.add_argument("--add-task", action="store_true", help="Add a new automation task")
    parser.add_argument("--run-task", metavar="TASK_ID", help="Run a specific task")
    parser.add_argument("--list-tasks", action="store_true", help="List all tasks")
    parser.add_argument("--run-all-tasks", action="store_true", help="Run all enabled tasks")
    parser.add_argument("--remove-task", metavar="TASK_ID", help="Remove a task")
    parser.add_argument("--enable-task", metavar="TASK_ID", help="Enable a task")
    parser.add_argument("--disable-task", metavar="TASK_ID", help="Disable a task")
    parser.add_argument("--task-logs", metavar="TASK_ID", help="Get task logs")
    
    # Task arguments
    parser.add_argument("--name", help="Task name")
    parser.add_argument("--script", help="Script path for automation task")
    parser.add_argument("--schedule", help="Task schedule (cron format)")
    parser.add_argument("--tasks-dir", default="/tmp/ilma_automation", help="Tasks directory")
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    try:
        # Server Monitoring
        if args.server_stats:
            monitor = ServerMonitor()
            stats = monitor.get_current_stats()
            
            print("\n=== Server Statistics ===")
            print(f"Timestamp: {stats['timestamp']}")
            
            print("\nCPU:")
            print(f"  Usage: {stats['cpu']['percent']:.1f}%")
            print(f"  Load Average: {stats['cpu']['load_average']}")
            
            print("\nMemory:")
            print(f"  Usage: {stats['memory']['percent']:.1f}%")
            print(f"  Used: {stats['memory']['used_gb']:.2f} GB / {stats['memory']['total_gb']:.2f} GB")
            
            print("\nDisk:")
            print(f"  Usage: {stats['disk']['percent']:.1f}%")
            print(f"  Used: {stats['disk']['used_gb']:.2f} GB / {stats['disk']['total_gb']:.2f} GB")
            
            print("\nNetwork:")
            print(f"  Sent: {stats['network']['sent_mb']:.2f} MB")
            print(f"  Received: {stats['network']['recv_mb']:.2f} MB")
            
            print(f"\nUptime: {stats['uptime_formatted']}")
        
        elif args.server_info:
            monitor = ServerMonitor()
            info = monitor.get_system_info()
            
            print("\n=== System Information ===")
            print(f"Hostname: {info['hostname']}")
            print(f"Platform: {info['platform']}")
            print(f"Python: {info['python_version'][:50]}...")
            print(f"CPU Cores: {info['cpu_count']} (Physical), {info['cpu_count_logical']} (Logical)")
            print(f"Boot Time: {info['boot_time']}")
            print(f"Total Processes: {info['process_count']}")
            
            if info.get('partitions'):
                print("\nDisk Partitions:")
                for part in info['partitions']:
                    print(f"  {part['device']} -> {part['mountpoint']} ({part['fstype']})")
                    print(f"    Total: {part['total_gb']:.2f} GB, Used: {part['used_gb']:.2f} GB ({part['percent']}%)")
        
        elif args.check_alerts:
            monitor = ServerMonitor()
            alerts = monitor.check_alerts()
            
            print("\n=== Alert Check ===")
            if alerts:
                print(f"Found {len(alerts)} alert(s):")
                for alert in alerts:
                    print(f"  [{alert['severity'].upper()}] {alert['message']}")
            else:
                print("No alerts triggered")
        
        elif args.metrics_history:
            monitor = ServerMonitor()
            history = monitor.get_metrics_history(limit=30)
            
            print("\n=== Recent Metrics History ===")
            print(f"Timestamp              | CPU%  | Mem%  | Disk%")
            print("-" * 50)
            for m in history:
                ts = m['timestamp'][11:19]  # Just time portion
                print(f"{ts} | {m['cpu_percent']:5.1f} | {m['memory_percent']:5.1f} | {m['disk_percent']:5.1f}")
        
        # Process Management
        elif args.process_list:
            manager = ProcessManager()
            processes = manager.list_processes(sort_by=args.sort, limit=args.limit or 50)
            
            print(f"\n=== Process List (sorted by {args.sort}) ===")
            print(f"{'PID':>8} | {'Name':<20} | {'CPU%':>6} | {'Mem%':>6} | {'Mem MB':>8} | Status")
            print("-" * 80)
            
            for proc in processes:
                print(f"{proc.pid:>8} | {proc.name[:20]:<20} | {proc.cpu_percent:>6.1f} | {proc.memory_percent:>6.1f} | {proc.memory_mb:>8.1f} | {proc.status.value}")
        
        elif args.process_info:
            manager = ProcessManager()
            proc = manager.get_process_by_pid(args.process_info)
            
            if proc:
                print(f"\n=== Process {args.process_info} ===")
                print(f"Name: {proc.name}")
                print(f"User: {proc.username}")
                print(f"Status: {proc.status.value}")
                print(f"CPU: {proc.cpu_percent:.1f}%")
                print(f"Memory: {proc.memory_percent:.1f}% ({proc.memory_mb:.1f} MB)")
                print(f"Started: {proc.create_time}")
                print(f"Command: {proc.command}")
            else:
                print(f"Process {args.process_info} not found")
        
        elif args.kill_process:
            manager = ProcessManager()
            success = manager.kill_process(args.kill_process, force=True)
            print(f"\nKill process {args.kill_process}: {'SUCCESS' if success else 'FAILED'}")
        
        elif args.kill_by_name:
            manager = ProcessManager()
            killed = manager.kill_by_name(args.kill_by_name)
            print(f"\nKilled {killed} process(es) matching '{args.kill_by_name}'")
        
        elif args.process_tree:
            manager = ProcessManager()
            tree = manager.get_process_tree(args.process_tree)
            
            if tree:
                print(f"\n=== Process Tree for PID {args.process_tree} ===")
                print(f"Process: {tree['name']} (PID: {tree['pid']})")
                if tree['children']:
                    print("Children:")
                    for child in tree['children']:
                        print(f"  - {child['name']} (PID: {child['pid']}, Status: {child['status']})")
                else:
                    print("No child processes")
            else:
                print(f"Process {args.process_tree} not found")
        
        # Automation
        elif args.add_task:
            if not args.name or not args.script:
                parser.error("--name and --script are required for adding a task")
            
            runner = AutomationRunner(tasks_dir=args.tasks_dir)
            task_id = runner.add_task(args.name, args.script, args.schedule)
            print(f"\nTask added: {task_id}")
        
        elif args.run_task:
            runner = AutomationRunner(tasks_dir=args.tasks_dir)
            result = runner.run_task(args.run_task)
            
            print(f"\n=== Task Execution: {result.get('task_name', 'Unknown')} ===")
            print(f"Success: {result['success']}")
            print(f"Execution Time: {result.get('execution_time', 0):.2f}s")
            print(f"Exit Code: {result.get('exit_code', 'N/A')}")
            if result.get('stderr'):
                print(f"Error: {result['stderr'][:500]}")
        
        elif args.list_tasks:
            runner = AutomationRunner(tasks_dir=args.tasks_dir)
            tasks = runner.list_tasks()
            
            print("\n=== Automation Tasks ===")
            for task in tasks:
                status_icon = "✓" if task['enabled'] else "✗"
                print(f"{status_icon} [{task['id']}] {task['name']}")
                print(f"    Script: {task['script']}")
                print(f"    Last Run: {task['last_run'] or 'Never'} - Status: {task['last_status'] or 'N/A'}")
        
        elif args.run_all_tasks:
            runner = AutomationRunner(tasks_dir=args.tasks_dir)
            results = runner.run_all()
            
            print(f"\n=== Ran {len(results)} Task(s) ===")
            for result in results:
                status = "✓" if result['success'] else "✗"
                print(f"{status} {result.get('task_name', 'Unknown')}: {'SUCCESS' if result['success'] else 'FAILED'}")
        
        elif args.remove_task:
            runner = AutomationRunner(tasks_dir=args.tasks_dir)
            success = runner.remove_task(args.remove_task)
            print(f"\nRemove task: {'SUCCESS' if success else 'FAILED'}")
        
        elif args.enable_task:
            runner = AutomationRunner(tasks_dir=args.tasks_dir)
            success = runner.enable_task(args.enable_task)
            print(f"\nEnable task: {'SUCCESS' if success else 'FAILED'}")
        
        elif args.disable_task:
            runner = AutomationRunner(tasks_dir=args.tasks_dir)
            success = runner.disable_task(args.disable_task)
            print(f"\nDisable task: {'SUCCESS' if success else 'FAILED'}")
        
        elif args.task_logs:
            runner = AutomationRunner(tasks_dir=args.tasks_dir)
            logs = runner.get_task_logs(args.task_logs)
            
            print(f"\n=== Logs for Task {args.task_logs} ===")
            for i, log in enumerate(logs):
                print(f"\n--- Log {i+1} ---")
                print(log[:1000])
        
        else:
            parser.print_help()
    
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()