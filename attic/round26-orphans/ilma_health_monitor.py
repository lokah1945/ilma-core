#!/usr/bin/env python3
"""
ILMA Health Monitor
====================
Runtime health tracker: monitors system health metrics, detects anomalies,
logs errors to .learnings/, and provides health scores.

Version: 1.0
"""

import json
import logging
import os
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

ILMA_ROOT = Path("/root/.hermes/profiles/ilma")
STATE_FILE = ILMA_ROOT / "ilma_model_router_data" / "model_health_state.json"


class HealthMonitor:
    """
    Runtime health monitor for ILMA.
    
    Tracks:
    - Model health state (circuit breaker status)
    - Wiring integrity
    - Learnings backlog
    - Disk usage
    - Git sync status
    
    Provides:
    - get_health_score() —0.0-1.0 overall score
    - get_health_report() — detailed report
    - detect_anomalies() — flag issues
    - log_anomaly() — auto-log to .learnings/
    """
    
    def __init__(self):
        self._last_check: Optional[datetime] = None
        self._cache_ttl = 60  # seconds
        self._cached_report: Optional[Dict] = None
    
    def get_health_score(self) -> float:
        """Get overall health score 0.0-1.0."""
        report = self.get_health_report()
        return report.get("health_score", 0.5)
    
    def get_health_report(self, force_refresh: bool = False) -> Dict[str, Any]:
        """Get full health report with all metrics."""
        now = time.time()
        
        if (not force_refresh
            and self._cached_report is not None
            and self._last_check is not None
            and (now - self._last_check.timestamp()) < self._cache_ttl):
            return self._cached_report
        
        report = {
            "timestamp": datetime.now().isoformat(),
            "health_score": 1.0,
            "components": {},
            "anomalies": [],
            "warnings": [],
        }
        
        #1. Model health state
        model_health = self._check_model_health()
        report["components"]["model_health"] = model_health
        
        # 2. Wiring integrity
        wiring = self._check_wiring()
        report["components"]["wiring"] = wiring
        
        # 3. Learnings backlog
        learnings = self._check_learnings()
        report["components"]["learnings"] = learnings
        
        # 4. Disk usage
        disk = self._check_disk()
        report["components"]["disk"] = disk
        
        # 5. Git sync
        git = self._check_git_sync()
        report["components"]["git"] = git

        # Calculate overall score
        scores = []
        for name, comp in report["components"].items():
            if isinstance(comp, dict) and "score" in comp:
                scores.append(comp["score"])
            elif isinstance(comp, dict) and "healthy" in comp:
                scores.append(1.0 if comp["healthy"] else 0.0)
        
        if scores:
            report["health_score"] = sum(scores) / len(scores)
        
        # Gather anomalies and warnings
        for comp in report["components"].values():
            if isinstance(comp, dict):
                if comp.get("anomaly"):
                    report["anomalies"].append(comp["anomaly"])
                report["warnings"].extend(comp.get("warnings", []))
        
        self._cached_report = report
        self._last_check = datetime.now()
        return report
    
    def detect_anomalies(self) -> List[Dict]:
        """Detect and return list of current anomalies."""
        report = self.get_health_report()
        anomalies = []
        
        for anomaly in report.get("anomalies", []):
            anomalies.append({
                "type": anomaly.get("type", "unknown"),
                "severity": anomaly.get("severity", "medium"),
                "message": anomaly.get("message", ""),
                "component": anomaly.get("component", "unknown"),
            })
        
        return anomalies
    
    def log_anomaly(self, anomaly_type: str, message: str, severity: str = "medium", component: str = "unknown"):
        """Log an anomaly to .learnings/ ERRORS.md."""
        try:
            from ilma_self_improvement import log_error
            log_error(
                summary=f"[{severity.upper()}] {anomaly_type} in {component}",
                error_detail=message,
                area=component,
                priority="high" if severity == "critical" else "medium",
            )
            logger.info(f"Logged anomaly: {anomaly_type} ({severity})")
        except Exception as e:
            logger.warning(f"Failed to log anomaly: {e}")
    
    # ─── COMPONENT CHECKS ────────────────────────────────────────────────────
    
    def _check_model_health(self) -> Dict[str, Any]:
        """Check model health state."""
        if not STATE_FILE.exists():
            return {"healthy": True, "score": 1.0, "message": "No state file"}
        
        try:
            raw = json.loads(STATE_FILE.read_text())
            # Health state schema: {"_meta":..., "providers":..., "models": {id: {...}}}.
            # Must iterate the nested models dict, not the 3 top-level keys (fixed 2026-06-20
            # audit: len(data)==3 made this check always report healthy).
            data = raw.get("models", raw) if isinstance(raw, dict) else {}
            data = {k: v for k, v in data.items() if isinstance(v, dict) and k != "_meta"}
            total = len(data)
            unavailable = sum(1 for v in data.values() if v.get("unavailable", False))
            rate = unavailable / total if total > 0 else 0
            
            healthy = rate < 0.5
            score = 1.0 - rate
            
            result = {
                "total_models": total,
                "unavailable": unavailable,
                "unavailable_rate": f"{rate:.1%}",
                "healthy": healthy,
                "score": score,
            }
            
            if rate > 0.8:
                result["anomaly"] = {
                    "type": "high_unavailable_rate",
                    "severity": "critical",
                    "message": f"{unavailable}/{total} models unavailable ({rate:.1%})",
                    "component": "model_health",
                }
            elif rate > 0.5:
                result["warnings"] = [f"{unavailable}/{total} models unavailable"]
            
            return result
        except Exception as e:
            return {"healthy": False, "score": 0.0, "error": str(e)}
    
    def _check_wiring(self) -> Dict[str, Any]:
        """Check runtime wiring."""
        wiring_path = ILMA_ROOT / "ilma_runtime_wiring.py"
        if not wiring_path.exists():
            return {"healthy": False, "score": 0.0, "error": "Wiring script missing"}
        
        try:
            result = subprocess.run(
                ["python3", str(wiring_path), "--verify"],
                capture_output=True, text=True, timeout=30, cwd=str(ILMA_ROOT)
            )
            output = result.stdout + result.stderr
            
            wired_m = __import__("re").search(r'"total_wired":\s*(\d+)', output)
            missing_m = __import__("re").search(r'"missing":\s*(\d+)', output)
            
            total_wired = int(wired_m.group(1)) if wired_m else 0
            missing = int(missing_m.group(1)) if missing_m else 0
            
            healthy = missing == 0 and total_wired >= 28
            score = total_wired /31.0 if total_wired > 0 else 0.0
            
            result = {
                "total_wired": total_wired,
                "missing": missing,
                "healthy": healthy,
                "score": score,
            }
            
            if missing > 0:
                result["warnings"] = [f"{missing} modules not wired"]
            
            return result
        except Exception as e:
            return {"healthy": False, "score": 0.0, "error": str(e)}
    
    def _check_learnings(self) -> Dict[str, Any]:
        """Check learnings backlog."""
        try:
            from ilma_self_improvement import get_learning_logger
            stats = get_learning_logger().get_stats()
            pending = sum(s.get("pending", 0) for s in stats.values())
            
            healthy = pending < 20
            score = max(0.0, 1.0 - pending / 20.0)
            
            result = {
                "pending": pending,
                "healthy": healthy,
                "score": score,
                "stats": stats,
            }
            
            if pending > 10:
                result["warnings"] = [f"{pending} pending learnings (backlog growing)"]
            
            return result
        except Exception as e:
            return {"healthy": False, "score": 0.0, "error": str(e)}
    
    def _check_disk(self) -> Dict[str, Any]:
        """Check disk usage."""
        try:
            result = subprocess.run(
                ["df", "-h", str(ILMA_ROOT)],
                capture_output=True, text=True, timeout=5
            )
            lines = result.stdout.strip().splitlines()
            if len(lines) >= 2:
                parts = lines[-1].split()
                use_pct = int(parts[4].rstrip("%"))
                
                healthy = use_pct < 90
                score = max(0.0, 1.0 - use_pct / 100.0)
                
                result = {
                    "usage_percent": use_pct,
                    "healthy": healthy,
                    "score": score,
                }
                
                if use_pct > 95:
                    result["anomaly"] = {
                        "type": "disk_near_full",
                        "severity": "critical",
                        "message": f"Disk {use_pct}% full",
                        "component": "disk",
                    }
                elif use_pct > 85:
                    result["warnings"] = [f"Disk {use_pct}% full"]
                
                return result
        except Exception as e:
            return {"healthy": True, "score": 1.0, "error": str(e)}
        
        return {"healthy": True, "score": 1.0}
    
    def _check_git_sync(self) -> Dict[str, Any]:
        """Check git sync status."""
        try:
            result = subprocess.run(
                ["git", "-C", str(ILMA_ROOT), "status", "--porcelain"],
                capture_output=True, text=True, timeout=5
            )
            dirty = len(result.stdout.strip().splitlines()) if result.stdout.strip() else 0
            
            healthy = dirty < 10
            score = max(0.0, 1.0 - dirty / 20.0)
            
            result = {
                "uncommitted_files": dirty,
                "healthy": healthy,
                "score": score,
            }
            
            if dirty > 20:
                result["warnings"] = [f"{dirty} uncommitted files (sync needed)"]
            
            return result
        except Exception as e:
            return {"healthy": True, "score": 1.0, "error": str(e)}


# ─── SINGLETON ────────────────────────────────────────────────────────────────

_global_monitor: Optional[HealthMonitor] = None


def get_health_monitor() -> HealthMonitor:
    """Get singleton HealthMonitor instance."""
    global _global_monitor
    if _global_monitor is None:
        _global_monitor = HealthMonitor()
    return _global_monitor


# ─── CLI ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    
    parser = argparse.ArgumentParser(description="ILMA Health Monitor")
    parser.add_argument("--report", action="store_true", help="Show full health report")
    parser.add_argument("--score", action="store_true", help="Show health score only")
    parser.add_argument("--anomalies", action="store_true", help="Show detected anomalies")
    args = parser.parse_args()
    
    monitor = get_health_monitor()
    
    if args.score:
        score = monitor.get_health_score()
        print(f"{score:.3f}")
    elif args.anomalies:
        for a in monitor.detect_anomalies():
            print(f"[{a['severity']}] {a['type']}: {a['message']}")
    elif args.report:
        print(json.dumps(monitor.get_health_report(), indent=2, default=str))
    else:
        score = monitor.get_health_score()
        status = "✅ HEALTHY" if score >= 0.8 else "⚠️  DEGRADED" if score >= 0.5 else "❌ UNHEALTHY"
        print(f"Health Score: {score:.3f} — {status}")
