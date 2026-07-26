#!/usr/bin/env python3
"""ILMA Rollback Script - Military Grade"""
import subprocess
import datetime
import sys


def rollback(deployment: str = "app") -> bool:
    """Rollback a Kubernetes deployment.
    
    Args:
        deployment: Name of the deployment to rollback
        
    Returns:
        True if successful, False otherwise
    """
    try:
        ver = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        result = subprocess.run(
            f"kubectl rollout undo deployment/{deployment}",
            shell=True,
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            print(f"✅ Rolled back {deployment} at {ver}")
            return True
        else:
            print(f"❌ Rollback failed: {result.stderr}")
            return False
    except Exception as e:
        print(f"❌ Rollback error: {e}")
        return False


if __name__ == "__main__":
    deployment = sys.argv[1] if len(sys.argv) > 1 else "app"
    success = rollback(deployment)
    sys.exit(0 if success else 1)
