#!/usr/bin/env python3
"""
ILMA Mission State Manager v2.0 — REAL MISSION STATE RUNTIME
Fixed: checkpoint now saves state_snapshot for true resume
Added: track system (add_track, update_track_status)
Added: evidence_id tracking, failure/recovery logging
"""
import argparse, json, os, sys, uuid
from datetime import datetime

class MissionStateManager:
    VERSION = "2.0"
    def __init__(self, state_dir):
        self.state_dir = state_dir
        os.makedirs(state_dir, exist_ok=True)
        self.state_file = os.path.join(state_dir, "mission_state.json")
        self.checkpoint_dir = os.path.join(state_dir, "checkpoints")
        os.makedirs(self.checkpoint_dir, exist_ok=True)

    def create_mission(self, mission_id, objective, checkpoint_interval=5):
        state = {
            "mission_id": mission_id,
            "objective": objective,
            "status": "active",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "checkpoint_interval": checkpoint_interval,
            "completed_units": [],
            "pending_units": [],
            "evidence_ids": [],
            "failures": [],
            "recovery_actions": [],
            "checkpoints": [],
            "tracks": []
        }
        self._save(state)
        print(f"Mission created: {mission_id}")

    def add_unit(self, unit_id, unit_type, description):
        state = self._load()
        state["pending_units"].append({
            "unit_id": unit_id,
            "type": unit_type,
            "description": description,
            "added_at": datetime.now().isoformat()
        })
        self._save(state)
        print(f"Unit added: {unit_id}")

    def add_track(self, track_id, track_name, track_type, target, metadata=None):
        """Add a mission track (e.g., longform_50p, codebase_100file)."""
        state = self._load()
        # Check duplicate
        for t in state.get("tracks", []):
            if t["track_id"] == track_id:
                print(f"Track already exists: {track_id}")
                return False
        track = {
            "track_id": track_id,
            "track_name": track_name,
            "track_type": track_type,
            "target": target,
            "status": "active",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "evidence_ids": [],
            "failures": [],
            "checkpoints": [],
            "metadata": metadata or {}
        }
        state.setdefault("tracks", []).append(track)
        self._save(state)
        print(f"Track added: {track_id} ({track_name})")
        return True

    def update_track_status(self, track_id, status, notes="", evidence_id=""):
        """Update track status: active, paused, completed, failed."""
        state = self._load()
        for t in state.get("tracks", []):
            if t["track_id"] == track_id:
                t["status"] = status
                t["updated_at"] = datetime.now().isoformat()
                if notes:
                    t.setdefault("notes", []).append({"timestamp": datetime.now().isoformat(), "notes": notes})
                if evidence_id:
                    t.setdefault("evidence_ids", []).append(evidence_id)
                self._save(state)
                print(f"Track {track_id} status → {status}")
                return True
        print(f"Track not found: {track_id}")
        return False

    def complete_unit(self, unit_id, evidence_id=""):
        state = self._load()
        for u in state["pending_units"]:
            if u["unit_id"] == unit_id:
                u["completed_at"] = datetime.now().isoformat()
                u["status"] = "completed"
                if evidence_id:
                    u["evidence_id"] = evidence_id
                    state["evidence_ids"].append(evidence_id)
                state["completed_units"].append(u)
                state["pending_units"].remove(u)
                break
        state["updated_at"] = datetime.now().isoformat()
        self._save(state)
        print(f"Unit completed: {unit_id}")

    def save_checkpoint(self, label="", track_id=""):
        state = self._load()
        cp_id = f"cp_{len(state['checkpoints'])+1:03d}_{datetime.now().strftime('%H%M%S')}"
        cp = {
            "checkpoint_id": cp_id,
            "label": label,
            "saved_at": datetime.now().isoformat(),
            "completed_count": len(state["completed_units"]),
            "pending_count": len(state["pending_units"]),
            # FIX: Include full state snapshot for true resume
            "state_snapshot": {
                "mission_id": state["mission_id"],
                "objective": state["objective"],
                "status": state["status"],
                "created_at": state["created_at"],
                "checkpoint_interval": state["checkpoint_interval"],
                "completed_units": list(state["completed_units"]),
                "pending_units": list(state["pending_units"]),
                "evidence_ids": list(state["evidence_ids"]),
                "failures": list(state["failures"]),
                "recovery_actions": list(state["recovery_actions"]),
                "tracks": list(state["tracks"])
            }
        }
        state["checkpoints"].append(cp)
        state["updated_at"] = datetime.now().isoformat()
        self._save(state)
        cp_path = os.path.join(self.checkpoint_dir, f"{cp_id}.json")
        with open(cp_path, "w") as f:
            json.dump(cp, f, indent=2)
        print(f"Checkpoint saved: {cp_id}")

        # If track specified, save track checkpoint too
        if track_id:
            for t in state.get("tracks", []):
                if t["track_id"] == track_id:
                    t["checkpoints"].append({
                        "checkpoint_id": cp_id,
                        "saved_at": datetime.now().isoformat(),
                        "label": label
                    })
                    t["updated_at"] = datetime.now().isoformat()
                    self._save(state)
                    break
        return cp_id

    def load_checkpoint(self, checkpoint_id):
        """Load checkpoint metadata from disk."""
        cp_path = os.path.join(self.checkpoint_dir, f"{checkpoint_id}.json")
        if not os.path.exists(cp_path):
            return None
        with open(cp_path) as f:
            return json.load(f)

    def resume_mission(self, checkpoint_id=""):
        """Resume mission from checkpoint — reloads state from disk."""
        cp_data = self.load_checkpoint(checkpoint_id)
        if not cp_data:
            print(f"No checkpoint found: {checkpoint_id}")
            return False

        # Reload fresh state from disk
        state = self._load()

        # Verify checkpoint exists in current state
        matching_cp = None
        for c in state.get("checkpoints", []):
            if c["checkpoint_id"] == (checkpoint_id or cp_data.get("checkpoint_id","")):
                matching_cp = c
                break

        if not matching_cp:
            # No matching checkpoint in current state — use the checkpoint file directly
            restored = cp_data.get("state_snapshot", {})
            for key in ["completed_units","pending_units","evidence_ids","failures","recovery_actions","tracks"]:
                if key in restored:
                    state[key] = restored[key]
            state["status"] = "resumed"
            state["resumed_from"] = cp_data.get("checkpoint_id","unknown")
            state["resumed_at"] = datetime.now().isoformat()
            self._save(state)
            print(f"Resumed from checkpoint file: {cp_data.get('checkpoint_id')}")
        else:
            # Checkpoint found in current state — restore from it
            restored = matching_cp.get("state_snapshot", {})
            if not restored:
                print("ERROR: checkpoint has no state_snapshot")
                return False
            for key in ["completed_units","pending_units","evidence_ids","failures","recovery_actions","tracks"]:
                if key in restored:
                    state[key] = restored[key]
            state["status"] = "resumed"
            state["resumed_from"] = matching_cp["checkpoint_id"]
            state["resumed_at"] = datetime.now().isoformat()
            self._save(state)

        print(f"Mission resumed successfully")
        print(f"  Completed units: {len(state['completed_units'])}")
        print(f"  Pending units: {len(state['pending_units'])}")
        print(f"  Tracks: {len(state.get('tracks', []))}")
        return True

    def record_failure(self, context, error_type, error_message, severity, recovery_needed, evidence_id=""):
        """Record a failure with full context."""
        state = self._load()
        record = {
            "timestamp": datetime.now().isoformat(),
            "context": context,
            "error_type": error_type,
            "error_message": error_message,
            "severity": severity,
            "recovery_needed": recovery_needed,
            "resolved": False
        }
        if evidence_id:
            record["evidence_id"] = evidence_id
            state["evidence_ids"].append(evidence_id)
        state["failures"].append(record)
        state["updated_at"] = datetime.now().isoformat()
        self._save(state)
        print(f"Failure recorded: [{severity}] {error_type} — {context}")
        return True

    def record_recovery(self, failure_context, action_taken, outcome, evidence_id=""):
        """Record recovery from a failure."""
        state = self._load()
        record = {
            "timestamp": datetime.now().isoformat(),
            "failure_context": failure_context,
            "action_taken": action_taken,
            "outcome": outcome,
            "resolved": True
        }
        if evidence_id:
            record["evidence_id"] = evidence_id
            state["evidence_ids"].append(evidence_id)
        state["recovery_actions"].append(record)

        # Mark corresponding failure as resolved
        for f in state["failures"]:
            if f.get("context") == failure_context and not f.get("resolved"):
                f["resolved"] = True
                f["recovery_action"] = action_taken
                f["recovery_outcome"] = outcome

        state["updated_at"] = datetime.now().isoformat()
        self._save(state)
        print(f"Recovery recorded: {failure_context[:50]} → {outcome}")
        return True

    def export_summary(self):
        state = self._load()
        summary = {
            "mission_id": state["mission_id"],
            "objective": state["objective"],
            "status": state["status"],
            "created_at": state["created_at"],
            "updated_at": state["updated_at"],
            "completed_units": len(state["completed_units"]),
            "pending_units": len(state["pending_units"]),
            "tracks": [
                {
                    "track_id": t["track_id"],
                    "track_name": t["track_name"],
                    "status": t["status"],
                    "target": t["target"]
                }
                for t in state.get("tracks", [])
            ],
            "checkpoints": len(state["checkpoints"]),
            "failures": len([f for f in state["failures"] if not f.get("resolved")]),
            "resolved_failures": len([f for f in state["failures"] if f.get("resolved")]),
            "evidence_ids": state["evidence_ids"]
        }
        summary_path = os.path.join(self.state_dir, "mission_summary.json")
        with open(summary_path, "w") as f:
            json.dump(summary, f, indent=2)
        print(f"Summary exported: {summary_path}")
        return summary_path

    def get_evidence_ids(self):
        state = self._load()
        return state.get("evidence_ids", [])

    def _load(self):
        if not os.path.exists(self.state_file):
            return {}
        with open(self.state_file) as f:
            return json.load(f)

    def _save(self, state):
        with open(self.state_file, "w") as f:
            json.dump(state, f, indent=2)

    def status(self):
        state = self._load()
        print(f"Mission: {state.get('mission_id','N/A')}")
        print(f"Status: {state.get('status','N/A')}")
        print(f"Completed: {len(state.get('completed_units',[]))}")
        print(f"Pending: {len(state.get('pending_units',[]))}")
        print(f"Tracks: {len(state.get('tracks',[]))}")
        print(f"Checkpoints: {len(state.get('checkpoints',[]))}")
        print(f"Failures: {len(state.get('failures',[]))} (resolved: {len([f for f in state.get('failures',[]) if f.get('resolved')])})")
        print(f"Evidence IDs: {len(state.get('evidence_ids',[]))}")

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--state-dir", default="./test_projects/phase5_mission_state")
    p.add_argument("--create", help="Create mission with ID")
    p.add_argument("--objective", default="Test mission")
    p.add_argument("--add-unit", help="Add unit with ID")
    p.add_argument("--unit-type", default="task")
    p.add_argument("--complete-unit", help="Complete unit with ID")
    p.add_argument("--add-track", help="Add track with ID")
    p.add_argument("--track-name", default="")
    p.add_argument("--track-type", default="")
    p.add_argument("--target", default="")
    p.add_argument("--update-track", help="Update track status")
    p.add_argument("--track-status", default="active")
    p.add_argument("--notes", default="")
    p.add_argument("--checkpoint", help="Save checkpoint with label")
    p.add_argument("--track", help="Track ID for checkpoint")
    p.add_argument("--resume", help="Resume from checkpoint ID")
    p.add_argument("--summary", action="store_true")
    p.add_argument("--status", action="store_true")
    p.add_argument("--failure", help="Record failure (format: context|error_type|message|severity|recovery)")
    p.add_argument("--recovery", help="Record recovery (format: context|action|outcome)")
    args = p.parse_args()

    mgr = MissionStateManager(args.state_dir)

    if args.create:
        mgr.create_mission(args.create, args.objective)
    elif args.add_unit:
        mgr.add_unit(args.add_unit, args.unit_type, args.add_unit)
    elif args.add_track:
        mgr.add_track(args.add_track, args.track_name, args.track_type, args.target)
    elif args.update_track:
        mgr.update_track_status(args.update_track, args.track_status, args.notes)
    elif args.complete_unit:
        mgr.complete_unit(args.complete_unit)
    elif args.checkpoint:
        mgr.save_checkpoint(args.checkpoint, args.track or "")
    elif args.resume is not None:
        mgr.resume_mission(args.resume if args.resume else "")
    elif args.summary:
        mgr.export_summary()
    elif args.status:
        mgr.status()
    elif args.failure:
        parts = args.failure.split("|")
        if len(parts) >= 5:
            mgr.record_failure(parts[0], parts[1], parts[2], parts[3], parts[4])
    elif args.recovery:
        parts = args.recovery.split("|")
        if len(parts) >= 3:
            mgr.record_recovery(parts[0], parts[1], parts[2])
    else:
        p.print_help()

if __name__ == "__main__":
    main()