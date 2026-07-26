#!/usr/bin/env python3
"""
ILMA GitHub Sync v1.0
=====================
GitHub synchronization for ILMA scripts and skills.

Based on: ILMA ILMA_github_sync.py patterns
"""
import os
import sys
import json
import time
import subprocess
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

WORKSPACE = Path("/root/.hermes/profiles/ilma")
GITHUB_DIR = WORKSPACE / ".github"
GITHUB_DIR.mkdir(parents=True, exist_ok=True)


class GitHubSync:
    """
    GitHub synchronization for ILMA.
    Manages remote repository connections and sync operations.
    """
    
    def __init__(self):
        self.config_file = GITHUB_DIR / "sync_config.json"
        self.sync_log_file = GITHUB_DIR / "sync_log.json"
        self.load_config()
        self.load_log()
    
    def load_config(self):
        """Load sync configuration."""
        if self.config_file.exists():
            try:
                with open(self.config_file) as f:
                    self.config = json.load(f)
            except ValueError:
                self.config = self._default_config()
        else:
            self.config = self._default_config()
    
    def _default_config(self) -> Dict:
        """Get default configuration."""
        return {
            "repo_url": "",
            "branch": "main",
            "auto_sync": False,
            "sync_interval": 3600,
            "last_sync": None,
            "sync_direction": "push",  # push, pull, bidirectional
            "include_patterns": ["*.py", "*.md", "*.yaml", "*.json"],
            "exclude_patterns": ["__pycache__", "*.pyc", ".git", "node_modules"]
        }
    
    def save_config(self):
        """Save sync configuration."""
        with open(self.config_file, "w") as f:
            json.dump(self.config, f, indent=2)
    
    def load_log(self):
        """Load sync log."""
        if self.sync_log_file.exists():
            try:
                with open(self.sync_log_file) as f:
                    self.sync_log = json.load(f)
            except ValueError:
                self.sync_log = []
        else:
            self.sync_log = []
    
    def save_log(self):
        """Save sync log."""
        with open(self.sync_log_file, "w") as f:
            json.dump(self.sync_log[-100:], f, indent=2)  # Keep last 100 entries
    
    def add_sync_entry(self, operation: str, status: str, details: str = ""):
        """Add an entry to the sync log."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "operation": operation,
            "status": status,
            "details": details
        }
        self.sync_log.append(entry)
        self.save_log()
    
    def configure(self, repo_url: str = None, branch: str = None, 
                  auto_sync: bool = None, sync_direction: str = None) -> Dict:
        """Configure GitHub sync."""
        if repo_url is not None:
            self.config["repo_url"] = repo_url
        if branch is not None:
            self.config["branch"] = branch
        if auto_sync is not None:
            self.config["auto_sync"] = auto_sync
        if sync_direction is not None:
            self.config["sync_direction"] = sync_direction
        
        self.save_config()
        self.add_sync_entry("configure", "success", "Configuration updated")
        
        return {"configured": True, "config": self.config}
    
    def check_connection(self) -> Dict:
        """Check GitHub connection status."""
        repo_url = self.config.get("repo_url", "")
        
        if not repo_url:
            return {
                "connected": False,
                "error": "No repository URL configured"
            }
        
        # Check if git is available
        try:
            result = subprocess.run(
                ["git", "--version"],
                capture_output=True,
                text=True
            )
            if result.returncode != 0:
                return {
                    "connected": False,
                    "error": "Git not installed"
                }
        except Exception:
            return {
                "connected": False,
                "error": "Git not available"
            }
        
        return {
            "connected": True,
            "repo_url": repo_url,
            "branch": self.config.get("branch", "main")
        }
    
    def push(self, message: str = None) -> Dict:
        """Push changes to remote."""
        if message is None:
            message = f"ILMA sync {datetime.now().isoformat()}"
        
        try:
            # Check git status
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                capture_output=True,
                text=True,
                cwd=WORKSPACE
            )
            
            if not result.stdout.strip():
                return {
                    "ok": True,
                    "message": "No changes to push",
                    "pushed": 0
                }
            
            # Add all changes
            subprocess.run(["git", "add", "-A"], cwd=WORKSPACE, capture_output=True)
            
            # Commit
            subprocess.run(
                ["git", "commit", "-m", message],
                cwd=WORKSPACE,
                capture_output=True
            )
            
            # Push (if remote exists)
            push_result = subprocess.run(
                ["git", "push", "origin", self.config.get("branch", "main")],
                cwd=WORKSPACE,
                capture_output=True,
                text=True
            )
            
            if push_result.returncode == 0:
                self.config["last_sync"] = datetime.now().isoformat()
                self.save_config()
                self.add_sync_entry("push", "success", message)
                
                return {
                    "ok": True,
                    "message": "Push successful",
                    "commit_message": message
                }
            else:
                self.add_sync_entry("push", "failed", push_result.stderr)
                return {
                    "ok": False,
                    "error": push_result.stderr
                }
        
        except Exception as e:
            self.add_sync_entry("push", "failed", str(e))
            return {
                "ok": False,
                "error": str(e)
            }
    
    def pull(self) -> Dict:
        """Pull changes from remote."""
        try:
            result = subprocess.run(
                ["git", "pull", "origin", self.config.get("branch", "main")],
                capture_output=True,
                text=True,
                cwd=WORKSPACE
            )
            
            if result.returncode == 0:
                self.config["last_sync"] = datetime.now().isoformat()
                self.save_config()
                self.add_sync_entry("pull", "success", "Pull successful")
                
                return {
                    "ok": True,
                    "message": "Pull successful",
                    "output": result.stdout[:500]
                }
            else:
                self.add_sync_entry("pull", "failed", result.stderr)
                return {
                    "ok": False,
                    "error": result.stderr
                }
        
        except Exception as e:
            self.add_sync_entry("pull", "failed", str(e))
            return {
                "ok": False,
                "error": str(e)
            }
    
    def sync(self) -> Dict:
        """Perform bidirectional sync."""
        direction = self.config.get("sync_direction", "push")
        
        if direction == "push":
            return self.push()
        elif direction == "pull":
            return self.pull()
        elif direction == "bidirectional":
            # Pull first, then push
            pull_result = self.pull()
            push_result = self.push()
            return {
                "pull": pull_result,
                "push": push_result
            }
        
        return {"ok": False, "error": "Invalid sync direction"}
    
    def get_status(self) -> Dict:
        """Get sync status."""
        connection = self.check_connection()
        
        return {
            "configured": bool(self.config.get("repo_url")),
            "connected": connection.get("connected", False),
            "repo_url": self.config.get("repo_url", ""),
            "branch": self.config.get("branch", "main"),
            "auto_sync": self.config.get("auto_sync", False),
            "last_sync": self.config.get("last_sync"),
            "sync_direction": self.config.get("sync_direction", "push"),
            "total_syncs": len(self.sync_log)
        }
    
    def get_log(self, limit: int = 20) -> List[Dict]:
        """Get sync log."""
        return self.sync_log[-limit:]


# ============================================================================
# CLI
# ============================================================================

def main():
    import argparse
    parser = argparse.ArgumentParser(description="ILMA GitHub Sync")
    parser.add_argument("command", nargs="?", default="status",
                        choices=["configure", "status", "push", "pull", "sync", "log"])
    parser.add_argument("--repo", type=str, help="Repository URL")
    parser.add_argument("--branch", type=str, help="Branch name")
    parser.add_argument("--auto", action="store_true", help="Enable auto sync")
    parser.add_argument("--direction", type=str, help="Sync direction (push, pull, bidirectional)")
    parser.add_argument("--message", type=str, help="Commit message")
    parser.add_argument("--limit", type=int, default=20, help="Log limit")
    
    sync = GitHubSync()
    args = parser.parse_args()
    
    if args.command == "configure":
        result = sync.configure(
            repo_url=args.repo,
            branch=args.branch,
            auto_sync=args.auto,
            sync_direction=args.direction
        )
        print(json.dumps(result, indent=2))
    
    elif args.command == "status":
        status = sync.get_status()
        print(json.dumps(status, indent=2))
    
    elif args.command == "push":
        result = sync.push(args.message)
        print(json.dumps(result, indent=2))
    
    elif args.command == "pull":
        result = sync.pull()
        print(json.dumps(result, indent=2))
    
    elif args.command == "sync":
        result = sync.sync()
        print(json.dumps(result, indent=2))
    
    elif args.command == "log":
        log = sync.get_log(args.limit)
        print(f"Recent {len(log)} sync operations:")
        for entry in log:
            status_icon = "✓" if entry["status"] == "success" else "✗"
            print(f"  {status_icon} [{entry['timestamp']}] {entry['operation']}: {entry['details'][:50]}...")

if __name__ == "__main__":
    main()
