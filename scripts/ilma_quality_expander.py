#!/usr/bin/env python3
"""
ILMA Quality Expander - Meningkatkan Kualitas Script
====================================================
Script untuk menambah fitur dan functionality dari script-script ILMA
agar kualitasnya menyamai atau melebihi ILMA.

Usage:
    python3 ilma_quality_expander.py expand <script_name>   # Expand single script
    python3 ilma_quality_expander.py all                   # Expand all scripts
    python3 ilma_quality_expander.py check                 # Check quality gaps
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from datetime import datetime

# ─── Paths ─────────────────────────────────────────────────────────────────
ILMA_SCRIPTS = Path("/root/.hermes/profiles/ilma/scripts")
ILMA_SCRIPTS = Path("/root/.hermes/profiles/ilma/scripts")

# ─── ANSI Colors ───────────────────────────────────────────────────────────
C_R = "\033[91m"; C_G = "\033[92m"; C_Y = "\033[93m"; C_B = "\033[94m"
C_C = "\033[96m"; C_BOLD = "\033[1m"; C_RESET = "\033[0m"
def c(t, col): return f"{col}{t}{C_RESET}"

# ─── Enhancement Templates ──────────────────────────────────────────────────
ENHANCEMENTS = {
    "error_handling": """
    # ─── Error Handling ────────────────────────────────────────────────────
    def handle_error(self, error: Exception, context: str = "") -> Dict[str, Any]:
        \"\"\"Handle errors gracefully with logging.\"\"\"
        error_info = {
            "error_type": type(error).__name__,
            "message": str(error),
            "context": context,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        self.logger.error(f"Error in {{context}}: {{error}}")
        return error_info
    
    def retry_on_failure(self, func: callable, max_attempts: int = 3, **kwargs) -> Any:
        \"\"\"Retry a function on failure with exponential backoff.\"\"\"
        for attempt in range(max_attempts):
            try:
                return func(**kwargs)
            except Exception as e:
                if attempt == max_attempts - 1:
                    raise
                wait_time = 2 ** attempt
                self.logger.warning(f"Attempt {{attempt+1}} failed, retrying in {{wait_time}}s...")
                time.sleep(wait_time)
""",
    
    "caching": """
    # ─── Caching ───────────────────────────────────────────────────────────
    _cache: Dict[str, Tuple[Any, float]] = {{}}
    _cache_ttl: float = 300.0  # 5 minutes default
    
    def get_cache(self, key: str) -> Optional[Any]:
        \"\"\"Get value from cache if not expired.\"\"\"
        if key in self._cache:
            value, timestamp = self._cache[key]
            if time.time() - timestamp < self._cache_ttl:
                return value
            del self._cache[key]
        return None
    
    def set_cache(self, key: str, value: Any, ttl: Optional[float] = None):
        \"\"\"Set value in cache with optional TTL.\"\"\"
        self._cache[key] = (value, time.time())
        if ttl:
            self._cache_ttl = ttl
    
    def clear_cache(self):
        \"\"\"Clear all cache.\"\"\"
        self._cache.clear()
""",
    
    "validation": """
    # ─── Input Validation ───────────────────────────────────────────────────
    def validate_input(self, data: Any, schema: Dict[str, Any]) -> bool:
        \"\"\"Validate input data against schema.\"\"\"
        for field, rules in schema.items():
            if rules.get("required") and field not in data:
                raise ValueError(f"Missing required field: {{field}}")
            if field in data:
                expected_type = rules.get("type")
                if expected_type and not isinstance(data[field], expected_type):
                    raise TypeError(f"Field {{field}} must be {{expected_type}}")
        return True
    
    def sanitize_input(self, data: str) -> str:
        \"\"\"Sanitize user input to prevent injection.\"\"\"
        # Remove potentially dangerous characters
        dangerous = ["<script", "eval(", "exec(", "{{", "}}"]
        for d in dangerous:
            data = data.replace(d, "")
        return data.strip()
""",
    
    "metrics": """
    # ─── Metrics Collection ────────────────────────────────────────────────
    _metrics: Dict[str, List[float]] = {{}}
    
    def record_metric(self, name: str, value: float):
        \"\"\"Record a metric value.\"\"\"
        if name not in self._metrics:
            self._metrics[name] = []
        self._metrics[name].append(value)
    
    def get_metric_stats(self, name: str) -> Dict[str, float]:
        \"\"\"Get statistics for a metric.\"\"\"
        if name not in self._metrics or not self._metrics[name]:
            return {{}}
        values = self._metrics[name]
        return {{
            "count": len(values),
            "min": min(values),
            "max": max(values),
            "avg": sum(values) / len(values)
        }}
    
    def get_all_metrics(self) -> Dict[str, Dict[str, float]]:
        \"\"\"Get all metric statistics.\"\"\"
        return {{name: self.get_metric_stats(name) for name in self._metrics}}
""",
    
    "progress_tracking": """
    # ─── Progress Tracking ─────────────────────────────────────────────────
    def __init__(self):
        self._progress: float = 0.0
        self._callbacks: List[callable] = []
    
    def add_progress_callback(self, callback: callable):
        \"\"\"Add a callback for progress updates.\"\"\"
        self._callbacks.append(callback)
    
    def update_progress(self, progress: float, message: str = ""):
        \"\"\"Update progress and notify callbacks.\"\"\"
        self._progress = max(0.0, min(1.0, progress))
        for callback in self._callbacks:
            callback(self._progress, message)
    
    def get_progress(self) -> float:
        \"\"\"Get current progress.\"\"\"
        return self._progress
"""
}

def log(msg, color=C_C):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"{color}[{ts}] {msg}{C_RESET}")

def check_quality():
    """Check quality gaps between ILMA and ILMA."""
    log("Checking quality gaps...", C_BOLD)
    
    ilma_scripts = list(ILMA_SCRIPTS.glob("ilma_*.py"))
    ILMA_avg = 0
    ILMA_total = 0
    ILMA_count = 0
    
    # Get ILMA average
    for script in ILMA_SCRIPTS.glob("ILMA_*.py"):
        size = script.stat().st_size
        ILMA_total += size
        ILMA_count += 1
    
    if ILMA_count > 0:
        ILMA_avg = ILMA_total / ILMA_count
    
    log(f"ILMA average script size: {ILMA_avg/1024:.1f}KB", C_C)
    
    # Check ILMA scripts
    log("\nILMA scripts needing enhancement:", C_Y)
    needs_enhancement = []
    
    for script in ilma_scripts:
        size = script.stat().st_size
        if size < ILMA_avg * 0.5:  # Less than 50% of ILMA average
            needs_enhancement.append((script.name, size))
    
    needs_enhancement.sort(key=lambda x: x[1])
    
    for name, size in needs_enhancement[:20]:
        log(f"  {name}: {size/1024:.1f}KB", C_Y)
    
    log(f"\nTotal scripts needing enhancement: {len(needs_enhancement)}", C_Y)
    
    return needs_enhancement

def expand_script(script_name: str, enhancements: list = None):
    """Add enhancements to a script."""
    script_path = ILMA_SCRIPTS / script_name
    
    if not script_path.exists():
        log(f"Script not found: {script_name}", C_R)
        return False
    
    content = script_path.read_text()
    original_size = len(content)
    
    # Check if already has enhancements
    if "def handle_error" in content:
        log(f"{script_name}: Already has error handling", C_Y)
        return False
    
    # Add enhancements
    added = []
    
    if enhancements is None:
        enhancements = ["error_handling", "caching", "validation"]
    
    for enhancement in enhancements:
        if enhancement in ENHANCEMENTS and ENHANCEMENTS[enhancement] not in content:
            content += ENHANCEMENTS[enhancement]
            added.append(enhancement)
    
    if added:
        script_path.write_text(content)
        new_size = len(content)
        log(f"✅ {script_name}: Added {', '.join(added)} (+{new_size-original_size} bytes)", C_G)
        return True
    else:
        log(f"⚠️ {script_name}: No enhancements added", C_Y)
        return False

def expand_all():
    """Enhance all scripts that need it."""
    log("Enhancing all scripts...", C_BOLD)
    
    needs_enhancement = check_quality()
    
    if not needs_enhancement:
        log("No scripts need enhancement!", C_G)
        return
    
    enhanced = 0
    for name, _ in needs_enhancement:
        if expand_script(name):
            enhanced += 1
    
    log(f"\n✅ Enhanced {enhanced} scripts", C_G)

def main():
    parser = argparse.ArgumentParser(description="ILMA Quality Expander")
    parser.add_argument("action", choices=["check", "expand", "all"])
    parser.add_argument("script", nargs="?", help="Script name to expand")
    args = parser.parse_args()
    
    if args.action == "check":
        check_quality()
    elif args.action == "expand":
        if not args.script:
            log("Error: script name required", C_R)
            sys.exit(1)
        expand_script(args.script)
    elif args.action == "all":
        expand_all()

if __name__ == "__main__":
    main()
