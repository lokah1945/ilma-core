#!/usr/bin/env python3
"""
ILMA Notification Dispatcher
Safely dispatches operational alerts via Webhooks.
"""

import os
import json
import urllib.request
from typing import Dict, Any

def send_alert(event_type: str, message: str, metadata: Dict[str, Any] = None):
    """
    Sends an alert securely. 
    Strict redaction applies: No raw prompts, no secrets, no diff contents.
    """
    webhook_url = os.environ.get("ILMA_WEBHOOK_URL")
    
    # Strip any potential secrets from metadata
    safe_metadata = {}
    if metadata:
        for k, v in metadata.items():
            if k in ["approval_id", "task_id", "domain", "risk_level", "fail_rate"]:
                safe_metadata[k] = v
                
    payload = {
        "event_type": event_type,
        "message": message[:500],  # Truncate to avoid accidental long-context leak
        "metadata": safe_metadata
    }
    
    print(f"[NOTIFICATION DISPATCH] {event_type} - {message[:50]}")
    
    if not webhook_url:
        print("[!] ILMA_WEBHOOK_URL not set. Falling back to local logging.")
        with open("/root/.hermes/profiles/ilma/logs/notifications.log", "a") as f:
            f.write(json.dumps(payload) + "\n")
        return

    try:
        req = urllib.request.Request(
            webhook_url,
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=5) as response:
            pass
    except Exception as e:
        print(f"[!] Notification failed: {e}")
        with open("/root/.hermes/profiles/ilma/logs/notifications.log", "a") as f:
            f.write(json.dumps(payload) + "\n")

if __name__ == "__main__":
    send_alert("test_alert", "This is a dry-run secure notification test.", {"risk_level": "low"})
