import json
import uuid
import time
import hashlib
from pathlib import Path
from typing import Dict, Any, Optional

QUEUE_FILE = Path("/root/.hermes/profiles/ilma/approval_queue.jsonl")

def get_hash(entry_dict: dict) -> str:
    # Ensure stable ordering for hash
    s = json.dumps({k: v for k, v in entry_dict.items() if k != "record_hash"}, sort_keys=True)
    return hashlib.sha256(s.encode()).hexdigest()

class ApprovalQueue:
    def __init__(self):
        self.queue_file = QUEUE_FILE
        if not self.queue_file.exists():
            self.queue_file.touch()

    def request_approval(self, task: str, domain: str, action: str, details: Dict[str, Any], risk_level: str) -> str:
        req_id = str(uuid.uuid4())[:8]
        valid_request = True
        validation_notes = []

        if risk_level in ["high", "critical"]:
            if "rollback_command" not in details or not details["rollback_command"]:
                valid_request = False
                validation_notes.append("Missing rollback command.")
            if "diff_summary" not in details or not details["diff_summary"]:
                valid_request = False
                validation_notes.append("Missing diff summary.")
        
        entry = {
            "approval_id": req_id,
            "task": task,
            "domain": domain,
            "action": action,
            "details": details,
            "risk_level": risk_level,
            "status": "pending" if valid_request else "rejected_pre_validation",
            "validation_notes": validation_notes,
            "created_at": time.time(),
            "expires_at": time.time() + 86400
        }
        entry["record_hash"] = get_hash(entry)

        with open(self.queue_file, "a") as f:
            f.write(json.dumps(entry) + "\n")
        return req_id

    def check_status(self, req_id: str) -> str:
        if not self.queue_file.exists(): return "unknown"
        status = "unknown"
        with open(self.queue_file, "r") as f:
            for line in f:
                if not line.strip(): continue
                data = json.loads(line)
                
                # Tamper evident check
                h = data.pop("record_hash", "")
                if get_hash(data) != h:
                    print(f"TAMPERING DETECTED on record {data.get('approval_id')}")
                    return "tampered"
                data["record_hash"] = h

                if data.get("approval_id") == req_id:
                    if data.get("status") == "pending" and time.time() > data.get("expires_at", 0):
                        return "expired"
                    status = data.get("status", "pending")
        return status

    def list_pending(self):
        pending = []
        if self.queue_file.exists():
            with open(self.queue_file, "r") as f:
                for line in f:
                    if not line.strip(): continue
                    data = json.loads(line)
                    if data.get("status") == "pending":
                        if time.time() > data.get("expires_at", 0):
                            data["status"] = "expired"
                            self.update_status(data["approval_id"], "expired")
                        else:
                            pending.append(data)
        return pending

    def update_status(self, req_id: str, new_status: str, notes: str = "", override_auth: str = ""):
        if not self.queue_file.exists(): return
        lines = []
        with open(self.queue_file, "r") as f:
            lines = f.readlines()
        with open(self.queue_file, "w") as f:
            for line in lines:
                if not line.strip(): continue
                data = json.loads(line)
                if data.get("approval_id") == req_id:
                    if data.get("risk_level") in ["high", "critical"] and new_status == "approved":
                        if override_auth != "CONFIRM_RISK":
                            print("High risk items require explicit override phrase: CONFIRM_RISK")
                            f.write(line)
                            continue
                            
                    if new_status == "approved" and data.get("status") == "rejected_pre_validation":
                        print("Cannot approve a request that failed pre-validation.")
                    else:
                        data["status"] = new_status
                        if notes: data["reviewer_notes"] = notes
                        
                        # Rehash
                        data.pop("record_hash", None)
                        data["record_hash"] = get_hash(data)
                f.write(json.dumps(data) + "\n")

    def show(self, req_id: str):
        if not self.queue_file.exists(): return None
        with open(self.queue_file, "r") as f:
            for line in f:
                if not line.strip(): continue
                data = json.loads(line)
                if data.get("approval_id") == req_id:
                    return data
        return None

if __name__ == "__main__":
    import sys
    q = ApprovalQueue()
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "list":
            for p in q.list_pending():
                print(f"[{p['approval_id']}] {p['domain']} - {p['action']} - Risk: {p['risk_level']}")
        elif cmd == "show" and len(sys.argv) > 2:
            print(json.dumps(q.show(sys.argv[2]), indent=2))
        elif cmd == "approve" and len(sys.argv) > 2:
            override = sys.argv[3] if len(sys.argv) > 3 else ""
            q.update_status(sys.argv[2], "approved", override_auth=override)
        elif cmd == "reject" and len(sys.argv) > 2:
            q.update_status(sys.argv[2], "rejected")
        elif cmd == "expire-stale":
            q.list_pending()
            print("Stale approvals expired.")
