#!/usr/bin/env python3
"""
ILMA Computer Use Agent v2.0
=============================

Uses ILMA Canonical Browser Engine (ilma_browser_engine.py).
All browser automation MUST go through this engine — no exceptions.

Usage:
    python3 ilma_computer_use_agent.py --task "Browse Google and search for x"
    python3 ilma_computer_use_agent.py --session lokah2150 --task "Check Gmail inbox"
"""

import asyncio
import json
import logging
import sys
import re
from pathlib import Path
from typing import Dict, List, Optional, Any

# Use canonical browser engine
sys.path.insert(0, str(Path(__file__).parent))
from ilma_browser_engine import BrowserEngine, activate_enforcement, STEALTH_ARGS, USER_AGENTS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Activate browser enforcement
activate_enforcement()


class BrowserResult:
    """Result container for browser operations."""
    def __init__(self, success: bool = False, final_url: str = "", final_title: str = "",
                 error: str = "", actions_executed: Optional[List] = None, dom_snapshots: Optional[List] = None):
        self.success = success
        self.final_url = final_url
        self.final_title = final_title
        self.error = error
        self.actions_executed = actions_executed or []
        self.dom_snapshots = dom_snapshots or []


class ILMAComputerUseAgent:
    """
    ILMA Computer Use Agent.
    
    Provides natural language interface to browser automation.
    Uses ILMA Canonical Browser Engine with stealth + CDP for undetectable browsing.
    Supports authenticated sessions via OpenClaw cookie storage.
    """
    
    def __init__(self, session_name: Optional[str] = None, fresh: bool = False, headless: bool = True):
        self.session_name = session_name or "lokah2150"
        self.fresh = fresh
        self.headless = headless
        self.engine: Optional[BrowserEngine] = None
        self.history: List[Dict[str, Any]] = []
    
    async def __aenter__(self) -> "ILMAComputerUseAgent":
        """Async context manager entry."""
        self.engine = BrowserEngine(
            headless=self.headless,
            stealth=True,
            cdp=True,
            session=self.session_name if not self.fresh else None,
        )
        await self.engine.initialize()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        if self.engine:
            await self.engine.close()
    
    async def execute_task(self, task: str) -> BrowserResult:
        """
        Execute a natural language task.
        """
        logger.info(f"Executing task: {task}")
        
        actions = self._parse_task(task)
        result = BrowserResult(success=True)
        
        for action in actions:
            action_result = await self._execute_action(action)
            result.actions_executed.append(action)
            
            if not action_result.get("success", False):
                result.success = False
                result.error = action_result.get("error", "Unknown error")
                break
            
            if self.engine and self.engine.page:
                result.final_url = self.engine.page.url
                try:
                    result.final_title = await self.engine.page.title()
                except Exception:
                    pass
        
        self.history.append({
            "task": task,
            "result": result.success,
            "url": result.final_url,
        })
        
        return result
    
    def _parse_task(self, task: str) -> List[Dict]:
        """Parse natural language task into browser actions."""
        actions = []
        task_lower = task.lower()
        
        # URL extraction
        url_match = re.search(r'https?://[^\s]+', task)
        if url_match:
            actions.append({
                "type": "goto",
                "target": url_match.group(0),
            })
        
        # Click actions
        if 'click' in task_lower or 'tekan' in task_lower:
            click_match = re.search(r'click (?:on |di )?["\']?([^"\']+)["\']?', task_lower)
            if click_match:
                target = click_match.group(1).strip()
                actions.append({
                    "type": "click",
                    "target": target if target.startswith('text=') or '/' in target else f"text={target}",
                })
        
        # Type actions
        if 'type' in task_lower or 'ketik' in task_lower or 'isi' in task_lower:
            type_match = re.search(r'(?:type|ketik|isi) ["\']([^"\']+)["\']?', task)
            value_match = re.search(r'(?:into|in) ["\']([^"\']+)["\']?', task)
            if type_match and value_match:
                actions.append({
                    "type": "type",
                    "target": value_match.group(1),
                    "value": type_match.group(1),
                })
        
        # Screenshot
        if 'screenshot' in task_lower or 'tangkap layar' in task_lower:
            actions.append({"type": "screenshot"})
        
        # Scroll
        if 'scroll' in task_lower:
            direction = 'down' if 'down' in task_lower else 'up'
            actions.append({"type": "scroll", "direction": direction})
        
        # Wait
        if 'wait' in task_lower or 'tunggu' in task_lower:
            actions.append({"type": "wait", "value": "2000"})
        
        # Default: just navigate to Google if no URL found
        if not actions:
            actions.append({"type": "goto", "target": "https://www.google.com"})
        
        return actions
    
    async def _execute_action(self, action: Dict) -> Dict:
        """Execute a single browser action."""
        if not self.engine:
            return {"success": False, "error": "Browser not initialized"}
        
        try:
            action_type = action.get("type", "")
            
            if action_type == "goto":
                target = action.get("target", "")
                result = await self.engine.navigate(target)
                return {"success": not bool(result.error), "error": result.error}
            
            elif action_type == "click":
                target = action.get("target", "")
                el = await self.engine.query_selector(target)
                if el:
                    await self.engine.click(el)
                    return {"success": True}
                return {"success": False, "error": f"Element not found: {target}"}
            
            elif action_type == "type":
                target = action.get("target", "")
                value = action.get("value", "")
                el = await self.engine.query_selector(target)
                if el:
                    await self.engine.type(el, value)
                    return {"success": True}
                return {"success": False, "error": f"Element not found: {target}"}
            
            elif action_type == "screenshot":
                path = f"/tmp/browser_screenshot_{int(asyncio.get_event_loop().time())}.png"
                await self.engine.screenshot(path)
                return {"success": True, "path": path}
            
            elif action_type == "scroll":
                direction = action.get("direction", "down")
                js = f"window.scrollBy(0, {300 if direction == 'down' else -300})"
                await self.engine.evaluate_js(js)
                return {"success": True}
            
            elif action_type == "wait":
                import time
                wait_ms = int(action.get("value", "1000"))
                time.sleep(wait_ms / 1000)
                return {"success": True}
            
            return {"success": True}
            
        except Exception as e:
            return {"success": False, "error": str(e)}


async def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="ILMA Computer Use Agent v2.0")
    parser.add_argument("--task", type=str, required=True, help="Task description")
    parser.add_argument("--session", type=str, help="Session name for authenticated browsing")
    parser.add_argument("--fresh", action="store_true", help="Use fresh anonymous session")
    parser.add_argument("--save", action="store_true", help="Save session after task")
    parser.add_argument("--visible", action="store_true", help="Show browser window")
    
    args = parser.parse_args()
    
    async with ILMAComputerUseAgent(
        session_name=args.session,
        fresh=args.fresh or not args.session,
        headless=not args.visible,
    ) as agent:
        result = await agent.execute_task(args.task)
        
        print(json.dumps({
            "success": result.success,
            "final_url": result.final_url,
            "final_title": result.final_title,
            "actions_count": len(result.actions_executed),
            "error": result.error,
        }, indent=2))


if __name__ == "__main__":
    asyncio.run(main())