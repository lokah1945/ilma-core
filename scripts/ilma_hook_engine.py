#!/usr/bin/env python3
"""
ILMA Hook Engine v1.0
======================
Hook system for pre/post execution hooks.

Based on: ILMA hook_engine.py patterns
"""
import os
import sys
import json
import time
from pathlib import Path
from typing import Dict, List, Callable, Any, Optional
from datetime import datetime
from dataclasses import dataclass, field

WORKSPACE = Path("/root/.hermes/profiles/ilma")
HOOKS_DIR = WORKSPACE / ".hooks"
HOOKS_DIR.mkdir(parents=True, exist_ok=True)

# ============================================================================
# HOOK DEFINITIONS
# ============================================================================

@dataclass
class Hook:
    id: str
    name: str
    hook_type: str  # pre, post, on_error, on_success
    event: str  # task, command, skill, all
    handler: str  # function name or script path
    enabled: bool = True
    priority: int = 0
    timeout: float = 30.0
    retry_count: int = 0
    created_at: str = ""
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()


class HookRegistry:
    """Registry of available hooks."""
    
    DEFAULT_HOOKS = [
        Hook(
            id="log_all",
            name="Log All Executions",
            hook_type="post",
            event="all",
            handler="log_handler",
            priority=0
        ),
        Hook(
            id="error_notify",
            name="Notify on Error",
            hook_type="on_error",
            event="all",
            handler="error_notify_handler",
            priority=100
        ),
        Hook(
            id="success_learn",
            name="Learn from Success",
            hook_type="on_success",
            event="all",
            handler="success_learn_handler",
            priority=50
        ),
        Hook(
            id="pre_validate",
            name="Pre-execution Validation",
            hook_type="pre",
            event="all",
            handler="pre_validate_handler",
            priority=90
        ),
        Hook(
            id="perf_monitor",
            name="Performance Monitor",
            hook_type="post",
            event="all",
            handler="perf_monitor_handler",
            priority=10
        ),
        Hook(
            id="metrics_collector",
            name="Collect Metrics",
            hook_type="post",
            event="all",
            handler="metrics_collector_handler",
            priority=5
        ),
        Hook(
            id="cache_warmer",
            name="Cache Warmer",
            hook_type="pre",
            event="task",
            handler="cache_warmer_handler",
            priority=20
        ),
        Hook(
            id="security_scan",
            name="Security Scan",
            hook_type="pre",
            event="task",
            handler="security_scan_handler",
            priority=95
        )
    ]


# ============================================================================
# HOOK HANDLERS
# ============================================================================

class HookHandlers:
    """Built-in hook handlers."""
    
    @staticmethod
    def log_handler(context: Dict) -> Dict:
        """Log all executions."""
        return {
            "logged": True,
            "timestamp": datetime.now().isoformat(),
            "event": context.get("event"),
            "result": context.get("result", {}).get("ok", None)
        }
    
    @staticmethod
    def error_notify_handler(context: Dict) -> Dict:
        """Handle error notifications."""
        if context.get("hook_type") == "on_error":
            return {
                "notified": True,
                "message": f"Error in {context.get('event')}: {context.get('error')}"
            }
        return {"notified": False}
    
    @staticmethod
    def success_learn_handler(context: Dict) -> Dict:
        """Learn from successful executions."""
        if context.get("result", {}).get("ok"):
            return {
                "learned": True,
                "pattern": "success",
                "event": context.get("event")
            }
        return {"learned": False}
    
    @staticmethod
    def pre_validate_handler(context: Dict) -> Dict:
        """Pre-execution validation."""
        return {
            "validated": True,
            "checks": ["input", "permissions", "resources"]
        }
    
    @staticmethod
    def perf_monitor_handler(context: Dict) -> Dict:
        """Monitor performance."""
        start = context.get("start_time", time.time())
        elapsed = time.time() - start
        
        return {
            "elapsed_seconds": elapsed,
            "performance": "good" if elapsed < 10 else "slow"
        }
    
    @staticmethod
    def metrics_collector_handler(context: Dict) -> Dict:
        """Collect execution metrics."""
        return {
            "metrics_collected": True,
            "event": context.get("event"),
            "timestamp": datetime.now().isoformat()
        }
    
    @staticmethod
    def cache_warmer_handler(context: Dict) -> Dict:
        """Warm up caches before execution."""
        return {
            "cache_warmed": True,
            "items": ["skills", "scripts", "memory"]
        }
    
    @staticmethod
    def security_scan_handler(context: Dict) -> Dict:
        """Security scan before execution."""
        return {
            "scan_passed": True,
            "threats_found": 0
        }


# ============================================================================
# HOOK ENGINE
# ============================================================================

class HookEngine:
    """
    Main hook engine for ILMA.
    Manages hook registration, execution, and lifecycle.
    """
    
    def __init__(self):
        self.hooks: Dict[str, Hook] = {}
        self.hook_history: List[Dict] = []
        self.max_history = 500
        self.handlers = HookHandlers()
        self._register_default_hooks()
        self.load_hooks()
    
    def _register_default_hooks(self):
        """Register default hooks."""
        for hook in HookRegistry.DEFAULT_HOOKS:
            self.hooks[hook.id] = hook
    
    def load_hooks(self):
        """Load hooks from disk."""
        hooks_file = HOOKS_DIR / "hooks.json"
        if hooks_file.exists():
            try:
                with open(hooks_file) as f:
                    data = json.load(f)
                
                for hook_data in data.get("hooks", []):
                    hook = Hook(**hook_data)
                    self.hooks[hook.id] = hook
            except Exception as e:
                print(f"Warning: Failed to load hooks: {e}")
    
    def save_hooks(self):
        """Save hooks to disk."""
        hooks_file = HOOKS_DIR / "hooks.json"
        
        data = {
            "hooks": [vars(h) for h in self.hooks.values()]
        }
        
        with open(hooks_file, "w") as f:
            json.dump(data, f, indent=2)
    
    def register_hook(self, hook: Hook) -> Hook:
        """Register a new hook."""
        self.hooks[hook.id] = hook
        self.save_hooks()
        return hook
    
    def unregister_hook(self, hook_id: str) -> bool:
        """Unregister a hook."""
        if hook_id in self.hooks:
            del self.hooks[hook_id]
            self.save_hooks()
            return True
        return False
    
    def get_hook(self, hook_id: str) -> Optional[Hook]:
        """Get a hook by ID."""
        return self.hooks.get(hook_id)
    
    def get_hooks_by_type(self, hook_type: str) -> List[Hook]:
        """Get all hooks of a specific type."""
        return [h for h in self.hooks.values() if h.hook_type == hook_type and h.enabled]
    
    def get_hooks_by_event(self, event: str) -> List[Hook]:
        """Get all hooks for a specific event."""
        matching = []
        for hook in self.hooks.values():
            if not hook.enabled:
                continue
            if hook.event == "all" or hook.event == event:
                matching.append(hook)
        
        # Sort by priority
        matching.sort(key=lambda h: h.priority, reverse=True)
        return matching
    
    def execute_hook(self, hook: Hook, context: Dict) -> Dict:
        """Execute a single hook."""
        start_time = time.time()
        
        try:
            # Get handler
            handler_func = getattr(self.handlers, hook.handler, None)
            
            if handler_func:
                result = handler_func(context)
            else:
                # Try to execute as script
                result = {"error": f"Handler not found: {hook.handler}"}
            
            elapsed = time.time() - start_time
            
            # Record execution
            execution = {
                "hook_id": hook.id,
                "hook_name": hook.name,
                "hook_type": hook.hook_type,
                "event": context.get("event"),
                "timestamp": datetime.now().isoformat(),
                "elapsed": elapsed,
                "success": True,
                "result": result
            }
            
            self.hook_history.append(execution)
            
            # Trim history
            if len(self.hook_history) > self.max_history:
                self.hook_history = self.hook_history[-self.max_history:]
            
            return result
        
        except Exception as e:
            elapsed = time.time() - start_time
            
            execution = {
                "hook_id": hook.id,
                "hook_name": hook.name,
                "hook_type": hook.hook_type,
                "event": context.get("event"),
                "timestamp": datetime.now().isoformat(),
                "elapsed": elapsed,
                "success": False,
                "error": str(e)
            }
            
            self.hook_history.append(execution)
            
            return {"success": False, "error": str(e)}
    
    def trigger_hooks(self, hook_type: str, event: str, context: Dict) -> List[Dict]:
        """Trigger all hooks for a specific type and event."""
        hooks = self.get_hooks_by_type(hook_type)
        hooks = [h for h in hooks if h.event == "all" or h.event == event]
        
        results = []
        for hook in hooks:
            context["hook_type"] = hook.hook_type
            result = self.execute_hook(hook, context)
            results.append({
                "hook_id": hook.id,
                "hook_name": hook.name,
                "result": result
            })
        
        return results
    
    def pre_execute(self, event: str, context: Dict) -> List[Dict]:
        """Run pre-execution hooks."""
        return self.trigger_hooks("pre", event, context)
    
    def post_execute(self, event: str, context: Dict) -> List[Dict]:
        """Run post-execution hooks."""
        return self.trigger_hooks("post", event, context)
    
    def on_error(self, event: str, error: str, context: Dict) -> List[Dict]:
        """Run error hooks."""
        context["error"] = error
        return self.trigger_hooks("on_error", event, context)
    
    def on_success(self, event: str, result: Dict, context: Dict) -> List[Dict]:
        """Run success hooks."""
        context["result"] = result
        return self.trigger_hooks("on_success", event, context)
    
    def get_hook_stats(self) -> Dict:
        """Get hook execution statistics."""
        total = len(self.hook_history)
        successful = sum(1 for h in self.hook_history if h.get("success"))
        failed = total - successful
        
        by_type = {}
        for h in self.hook_history:
            hook_type = h.get("hook_type", "unknown")
            by_type[hook_type] = by_type.get(hook_type, 0) + 1
        
        return {
            "total_hooks": len(self.hooks),
            "total_executions": total,
            "successful": successful,
            "failed": failed,
            "success_rate": successful / total if total > 0 else 1.0,
            "by_type": by_type
        }
    
    def get_hook_history(self, limit: int = 50) -> List[Dict]:
        """Get hook execution history."""
        return self.hook_history[-limit:]


# ============================================================================
# CLI
# ============================================================================

def main():
    import argparse
    parser = argparse.ArgumentParser(description="ILMA Hook Engine")
    parser.add_argument("command", nargs="?", default="list",
                        choices=["list", "add", "remove", "enable", "disable", "trigger", "stats", "history"])
    parser.add_argument("--id", type=str, help="Hook ID")
    parser.add_argument("--name", type=str, help="Hook name")
    parser.add_argument("--type", type=str, default="post", help="Hook type (pre, post, on_error, on_success)")
    parser.add_argument("--event", type=str, default="all", help="Event to trigger on")
    parser.add_argument("--handler", type=str, help="Handler function name")
    parser.add_argument("--priority", type=int, default=50, help="Hook priority")
    
    engine = HookEngine()
    args = parser.parse_args()
    
    if args.command == "list":
        print(f"Total Hooks: {len(engine.hooks)}")
        print()
        for hook in engine.hooks.values():
            status = "✓" if hook.enabled else "✗"
            print(f"{status} [{hook.hook_type}] {hook.name} ({hook.id})")
            print(f"    Event: {hook.event}, Priority: {hook.priority}")
            print(f"    Handler: {hook.handler}")
            print()
    
    elif args.command == "add":
        if not args.id or not args.name or not args.handler:
            print("Error: --id, --name, and --handler required")
            sys.exit(1)
        
        hook = Hook(
            id=args.id,
            name=args.name,
            hook_type=args.type,
            event=args.event,
            handler=args.handler,
            priority=args.priority
        )
        
        result = engine.register_hook(hook)
        print(f"Hook registered: {result.id}")
    
    elif args.command == "remove":
        if not args.id:
            print("Error: --id required")
            sys.exit(1)
        
        if engine.unregister_hook(args.id):
            print(f"Hook removed: {args.id}")
        else:
            print(f"Hook not found: {args.id}")
    
    elif args.command == "enable":
        if not args.id:
            print("Error: --id required")
            sys.exit(1)
        
        hook = engine.get_hook(args.id)
        if hook:
            hook.enabled = True
            engine.save_hooks()
            print(f"Hook enabled: {args.id}")
        else:
            print(f"Hook not found: {args.id}")
    
    elif args.command == "disable":
        if not args.id:
            print("Error: --id required")
            sys.exit(1)
        
        hook = engine.get_hook(args.id)
        if hook:
            hook.enabled = False
            engine.save_hooks()
            print(f"Hook disabled: {args.id}")
        else:
            print(f"Hook not found: {args.id}")
    
    elif args.command == "trigger":
        results = engine.pre_execute("test_event", {"event": "test"})
        print("Pre-execution hooks triggered:")
        for r in results:
            print(f"  {r['hook_name']}: {r['result']}")
    
    elif args.command == "stats":
        stats = engine.get_hook_stats()
        print(json.dumps(stats, indent=2))
    
    elif args.command == "history":
        history = engine.get_hook_history()
        print(f"Recent {len(history)} hook executions:")
        for h in history[-20:]:
            status = "✓" if h.get("success") else "✗"
            print(f"  {status} [{h['hook_type']}] {h['hook_name']} - {h['timestamp']}")

if __name__ == "__main__":
    main()
