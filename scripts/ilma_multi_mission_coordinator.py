#!/usr/bin/env python3
"""
ILMA Multi-Mission Coordinator
Handles multiple missions with cross-dependencies, shared evidence, shared buffer,
conflict detection, global checkpoint/resume, and global quality gate.

Phase 41C - Multi-Mission Orchestration
stdlib-only, local, deterministic.
"""
import os
import json
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from enum import Enum

STATE_DIR = "/root/.hermes/profiles/ilma/state/multi_mission"
COHORT_DIR = "/root/.hermes/profiles/ilma/state/multi_mission/cohorts"

@dataclass
class MissionPriority(Enum):
    """Mission priority enum."""
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4

@dataclass
class MissionStatus(Enum):
    """Mission status enum."""
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    BLOCKED = "BLOCKED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

@dataclass
class DependencyType(Enum):
    """Dependency type enum."""
    CONSUMES = "CONSUMES"   # Mission A needs Mission B's output
    BLOCKS = "BLOCKS"       # Mission A blocks Mission B
    SHARES = "SHARES"       # Mission A and B share something

@dataclass
class ConflictType(Enum):
    """Conflict type enum."""
    EVIDENCE_CONFLICT = "EVIDENCE_CONFLICT"
    BUFFER_OVERWRITE = "BUFFER_OVERWRITE"
    CONTRADICTION = "CONTRADICTION"
    OS_BUILD_FALSE_CLAIM = "OS_BUILD_FALSE_CLAIM"
    INVALID_EVIDENCE = "INVALID_EVIDENCE"

@dataclass
class CrossDependency:
    """Cross-mission dependency."""
    dep_id: str
    source_mission: str
    target_mission: str
    dep_type: str
    reason: str
    satisfied: bool = False

@dataclass
class SharedEvidence:
    """Shared evidence item."""
    evidence_id: str
    description: str
    source_path: str
    supported_missions: List[str]
    created_at: str
    created_by: str

@dataclass
class SharedBufferEntry:
    """Shared buffer entry."""
    key: str
    value: Any
    source_mission: str
    timestamp: str
    previous_value: Any = None
    overwritten: bool = False

@dataclass
class Conflict:
    """Conflict entry."""
    conflict_id: str
    conflict_type: str
    missions_involved: List[str]
    description: str
    severity: str
    detected_at: str
    resolved: bool = False
    resolution: str = ""

@dataclass
class QualityGateResult:
    """Quality gate result."""
    gate_name: str
    status: str  # PASS, WARN, FAIL
    evidence: str = ""
    notes: str = ""

@dataclass
class Mission:
    """Mission in cohort."""
    mission_id: str
    target_type: str  # LONGFORM, CODEBASE, RESEARCH, LINUX_DISTRO
    goal: str
    priority: str
    status: str
    blocked_reason: str = ""
    quality_gates: List[Dict] = field(default_factory=list)
    evidence_ids: List[str] = field(default_factory=list)
    stages: List[str] = field(default_factory=list)
    checkpoint_id: Optional[str] = None

@dataclass
class GlobalCheckpoint:
    """Global checkpoint."""
    checkpoint_id: str
    label: str
    timestamp: str
    mission_states: Dict[str, Dict]
    dependencies: List[Dict]
    shared_buffer: Dict[str, Any]
    shared_evidence: List[Dict]
    conflicts: List[Dict]
    created_at: str

class MultiMissionCoordinator:
    """
    Multi-Mission Coordinator for ILMA Phase 41.
    Manages multiple missions with cross-dependencies, shared evidence, shared buffer,
    conflict detection, global checkpoint/resume, and global quality gate.
    """

    def __init__(self, cohort_id: str, description: str = ""):
        self.cohort_id = cohort_id
        self.description = description
        self.missions: Dict[str, Mission] = {}
        self.cross_dependencies: List[CrossDependency] = []
        self.shared_evidence: List[SharedEvidence] = []
        self.shared_buffer: Dict[str, SharedBufferEntry] = {}
        self.conflicts: List[Conflict] = []
        self.checkpoints: List[GlobalCheckpoint] = []
        self.created_at = datetime.now(timezone.utc).isoformat()
        self.updated_at = self.created_at

    # === Cohort Management ===

    def create_cohort(self, cohort_id: str, description: str = "") -> str:
        """Create a new cohort (constructor already does this)."""
        self.cohort_id = cohort_id
        self.description = description
        self.created_at = datetime.now(timezone.utc).isoformat()
        self.updated_at = self.created_at
        return cohort_id

    def get_cohort_info(self) -> Dict:
        """Get cohort info."""
        return {
            "cohort_id": self.cohort_id,
            "description": self.description,
            "missions": len(self.missions),
            "dependencies": len(self.cross_dependencies),
            "shared_evidence": len(self.shared_evidence),
            "shared_buffer_keys": len(self.shared_buffer),
            "conflicts": len(self.conflicts),
            "checkpoints": len(self.checkpoints),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    # === Mission Management ===

    def add_mission(self, mission_id: str, target_type: str, priority: str = "MEDIUM",
                    goal: str = "", stages: List[str] = None) -> Mission:
        """Add a mission to the cohort."""
        if mission_id in self.missions:
            raise ValueError(f"Mission {mission_id} already exists")
        if stages is None:
            stages = ["STAGE_1", "STAGE_2", "STAGE_3"]
        mission = Mission(
            mission_id=mission_id,
            target_type=target_type,
            goal=goal or f"{target_type} mission",
            priority=priority,
            status="PENDING",
            stages=stages
        )
        self.missions[mission_id] = mission
        self.updated_at = datetime.now(timezone.utc).isoformat()
        return mission

    def get_mission(self, mission_id: str) -> Optional[Mission]:
        """Get mission by ID."""
        return self.missions.get(mission_id)

    def update_mission_status(self, mission_id: str, status: str,
                               blocked_reason: str = "") -> bool:
        """Update mission status."""
        if mission_id not in self.missions:
            return False
        self.missions[mission_id].status = status
        self.missions[mission_id].blocked_reason = blocked_reason
        self.updated_at = datetime.now(timezone.utc).isoformat()
        return True

    def add_mission_evidence(self, mission_id: str, evidence_id: str) -> bool:
        """Add evidence to mission."""
        if mission_id not in self.missions:
            return False
        if evidence_id not in self.missions[mission_id].evidence_ids:
            self.missions[mission_id].evidence_ids.append(evidence_id)
            self.updated_at = datetime.now(timezone.utc).isoformat()
        return True

    # === Cross-Dependency Management ===

    def add_cross_dependency(self, source_mission: str, target_mission: str,
                             dep_type: str, reason: str = "") -> CrossDependency:
        """Add cross-mission dependency."""
        if source_mission not in self.missions:
            raise ValueError(f"Source mission {source_mission} not found")
        if target_mission not in self.missions:
            raise ValueError(f"Target mission {target_mission} not found")

        dep = CrossDependency(
            dep_id=f"DEP-{uuid.uuid4().hex[:8]}",
            source_mission=source_mission,
            target_mission=target_mission,
            dep_type=dep_type,
            reason=reason,
            satisfied=False
        )
        self.cross_dependencies.append(dep)
        self.updated_at = datetime.now(timezone.utc).isoformat()
        return dep

    def check_cycle(self) -> List[str]:
        """Check for dependency cycles."""
        # Simple cycle detection using DFS
        visited = set()
        rec_stack = set()
        cycle_path = []

        def dfs(node: str) -> bool:
            visited.add(node)
            rec_stack.add(node)
            cycle_path.append(node)

            # Find dependencies where this mission is target
            for dep in self.cross_dependencies:
                if dep.target_mission == node:
                    neighbor = dep.source_mission
                    if neighbor not in visited:
                        if dfs(neighbor):
                            return True
                    elif neighbor in rec_stack:
                        cycle_path.append(neighbor)
                        return True

            cycle_path.pop()
            rec_stack.remove(node)
            return False

        for mission_id in self.missions:
            if mission_id not in visited:
                if dfs(mission_id):
                    return cycle_path
        return []

    # === Shared Evidence ===

    def add_shared_evidence(self, evidence_id: str, mission_ids: List[str],
                            description: str = "", source_path: str = "",
                            created_by: str = "coordinator") -> SharedEvidence:
        """Add shared evidence."""
        # Check for duplicate evidence_id
        for ev in self.shared_evidence:
            if ev.evidence_id == evidence_id:
                raise ValueError(f"Evidence ID {evidence_id} already exists")

        evidence = SharedEvidence(
            evidence_id=evidence_id,
            description=description,
            source_path=source_path,
            supported_missions=mission_ids,
            created_at=datetime.now(timezone.utc).isoformat(),
            created_by=created_by
        )
        self.shared_evidence.append(evidence)

        # Add to each mission's evidence list
        for mission_id in mission_ids:
            self.add_mission_evidence(mission_id, evidence_id)

        self.updated_at = datetime.now(timezone.utc).isoformat()
        return evidence

    def get_evidence_for_mission(self, mission_id: str) -> List[SharedEvidence]:
        """Get all evidence supporting a mission."""
        return [ev for ev in self.shared_evidence if mission_id in ev.supported_missions]

    # === Shared Working Buffer ===

    def add_shared_buffer(self, key: str, value: Any, source_mission: str) -> SharedBufferEntry:
        """Add to shared working buffer."""
        entry = SharedBufferEntry(
            key=key,
            value=value,
            source_mission=source_mission,
            timestamp=datetime.now(timezone.utc).isoformat(),
            previous_value=None,
            overwritten=False
        )

        if key in self.shared_buffer:
            # Overwrite detected
            entry.previous_value = self.shared_buffer[key].value
            entry.overwritten = True

        self.shared_buffer[key] = entry
        self.updated_at = datetime.now(timezone.utc).isoformat()
        return entry

    def get_shared_buffer(self, key: str) -> Optional[Any]:
        """Get value from shared buffer."""
        if key in self.shared_buffer:
            return self.shared_buffer[key].value
        return None

    def get_buffer_audit_log(self) -> List[Dict]:
        """Get buffer audit log (overwrites only)."""
        return [
            {
                "key": k,
                "previous_value": v.previous_value,
                "new_value": v.value,
                "source_mission": v.source_mission,
                "timestamp": v.timestamp,
                "overwritten": v.overwritten
            }
            for k, v in self.shared_buffer.items()
            if v.overwritten
        ]

    # === Conflict Detection ===

    def detect_conflicts(self) -> List[Conflict]:
        """Detect all types of conflicts."""
        self.conflicts = []

        # 1. Buffer overwrite conflicts
        for key, entry in self.shared_buffer.items():
            if entry.overwritten:
                conflict = Conflict(
                    conflict_id=f"CONF-{uuid.uuid4().hex[:8]}",
                    conflict_type="BUFFER_OVERWRITE",
                    missions_involved=[entry.source_mission],
                    description=f"Key '{key}' overwritten by {entry.source_mission}",
                    severity="MEDIUM",
                    detected_at=datetime.now(timezone.utc).isoformat()
                )
                self.conflicts.append(conflict)

        # 2. OS build false claim detection
        build_key = self.get_shared_buffer("os_build_executed")
        design_key = self.get_shared_buffer("linux_distro_design_only")
        if build_key == True and design_key == True:
            conflict = Conflict(
                conflict_id=f"CONF-{uuid.uuid4().hex[:8]}",
                conflict_type="OS_BUILD_FALSE_CLAIM",
                missions_involved=["LINUX_DISTRO"],
                description="OS build marked as EXECUTED but design-only plan says NO build",
                severity="HIGH",
                detected_at=datetime.now(timezone.utc).isoformat()
            )
            self.conflicts.append(conflict)

        # 3. Source count contradiction (LONGFORM vs RESEARCH)
        longform_count = self.get_shared_buffer("source_count_longform")
        research_count = self.get_shared_buffer("source_count_research")
        if longform_count and research_count and longform_count != research_count:
            conflict = Conflict(
                conflict_id=f"CONF-{uuid.uuid4().hex[:8]}",
                conflict_type="CONTRADICTION",
                missions_involved=["LONGFORM_MINI_V2", "RESEARCH_MINI_V2"],
                description=f"Source count contradiction: longform={longform_count}, research={research_count}",
                severity="MEDIUM",
                detected_at=datetime.now(timezone.utc).isoformat()
            )
            self.conflicts.append(conflict)

        return self.conflicts

    def get_unresolved_conflicts(self) -> List[Conflict]:
        """Get unresolved conflicts."""
        return [c for c in self.conflicts if not c.resolved]

    # === Blocked Mission Detection ===

    def detect_blocked_missions(self) -> List[str]:
        """Detect blocked missions."""
        blocked = []

        for mission_id, mission in self.missions.items():
            if mission.status in ["COMPLETED", "FAILED"]:
                continue

            # Check dependencies
            for dep in self.cross_dependencies:
                if dep.target_mission == mission_id and dep.dep_type == "CONSUMES":
                    source_mission = self.missions.get(dep.source_mission)
                    if not source_mission or source_mission.status != "COMPLETED":
                        if mission_id not in blocked:
                            blocked.append(mission_id)
                            mission.status = "BLOCKED"
                            mission.blocked_reason = f"Waiting for {dep.source_mission} ({dep.dep_type})"

        return blocked

    # === Global Checkpoint/Resume ===

    def checkpoint_cohort(self, label: str = "") -> GlobalCheckpoint:
        """Create global checkpoint of all state."""
        checkpoint = GlobalCheckpoint(
            checkpoint_id=f"CP-{uuid.uuid4().hex[:8]}",
            label=label,
            timestamp=datetime.now(timezone.utc).isoformat(),
            mission_states={
                mid: {
                    "status": m.status,
                    "priority": m.priority,
                    "quality_gates": m.quality_gates,
                    "evidence_ids": m.evidence_ids,
                    "stages": m.stages,
                    "checkpoint_id": m.checkpoint_id,
                    "blocked_reason": m.blocked_reason
                }
                for mid, m in self.missions.items()
            },
            dependencies=[asdict(d) for d in self.cross_dependencies],
            shared_buffer={
                k: {
                    "key": v.key,
                    "value": v.value,
                    "source_mission": v.source_mission,
                    "timestamp": v.timestamp,
                    "overwritten": v.overwritten
                }
                for k, v in self.shared_buffer.items()
            },
            shared_evidence=[asdict(e) for e in self.shared_evidence],
            conflicts=[asdict(c) for c in self.conflicts],
            created_at=datetime.now(timezone.utc).isoformat()
        )
        self.checkpoints.append(checkpoint)
        return checkpoint

    def resume_cohort(self, checkpoint_id: str) -> bool:
        """Resume cohort from checkpoint."""
        cp = None
        for c in self.checkpoints:
            if c.checkpoint_id == checkpoint_id:
                cp = c
                break

        if not cp:
            return False

        # Restore mission states
        for mid, state in cp.mission_states.items():
            if mid in self.missions:
                self.missions[mid].status = state["status"]
                self.missions[mid].priority = state["priority"]
                self.missions[mid].quality_gates = state["quality_gates"]
                self.missions[mid].evidence_ids = state["evidence_ids"]
                self.missions[mid].stages = state["stages"]
                self.missions[mid].checkpoint_id = state["checkpoint_id"]
                self.missions[mid].blocked_reason = state.get("blocked_reason", "")

        # Restore dependencies
        self.cross_dependencies = [
            CrossDependency(**d) for d in cp.dependencies
        ]

        # Restore shared buffer
        self.shared_buffer = {}
        for k, v in cp.shared_buffer.items():
            entry = SharedBufferEntry(
                key=v["key"],
                value=v["value"],
                source_mission=v["source_mission"],
                timestamp=v["timestamp"],
                overwritten=v.get("overwritten", False)
            )
            self.shared_buffer[k] = entry

        # Restore shared evidence
        self.shared_evidence = [
            SharedEvidence(**e) for e in cp.shared_evidence
        ]

        # Restore conflicts
        self.conflicts = [
            Conflict(**c) for c in cp.conflicts
        ]

        self.updated_at = datetime.now(timezone.utc).isoformat()
        return True

    # === Quality Gates ===

    def add_quality_gate(self, mission_id: str, gate_name: str,
                         status: str, evidence: str = "", notes: str = "") -> bool:
        """Add quality gate result to mission."""
        if mission_id not in self.missions:
            return False

        gate = {
            "gate_name": gate_name,
            "status": status,
            "evidence": evidence,
            "notes": notes
        }
        self.missions[mission_id].quality_gates.append(gate)
        self.updated_at = datetime.now(timezone.utc).isoformat()
        return True

    def run_global_quality_gate(self) -> Dict:
        """Run global quality gate on cohort."""
        result = {
            "status": "PASS",
            "checks": [],
            "warnings": [],
            "failures": [],
            "summary": ""
        }

        # Check 1: All missions have final status
        no_status = [mid for mid, m in self.missions.items()
                     if m.status in ["PENDING"] and mid not in ["LONGFORM_MINI_V2"]]
        if no_status:
            result["warnings"].append(f"Missions without final status: {no_status}")

        # Check 2: Dependencies resolved or blocked honestly
        unresolved_deps = []
        for dep in self.cross_dependencies:
            if dep.dep_type == "CONSUMES":
                source = self.missions.get(dep.source_mission)
                if not source or source.status != "COMPLETED":
                    unresolved_deps.append(f"{dep.source_mission} -> {dep.target_mission}")

        if unresolved_deps:
            result["warnings"].append(f"Unresolved dependencies: {unresolved_deps}")

        # Check 3: Shared evidence valid
        invalid_evidence = []
        for ev in self.shared_evidence:
            if not ev.source_path:
                invalid_evidence.append(ev.evidence_id)
        if invalid_evidence:
            result["failures"].append(f"Invalid evidence (no source_path): {invalid_evidence}")
            result["status"] = "FAIL"

        # Check 4: No unresolved conflicts
        unresolved = self.get_unresolved_conflicts()
        if unresolved:
            high_severity = [c for c in unresolved if c.severity == "HIGH"]
            if high_severity:
                result["failures"].append(f"Unresolved HIGH severity conflicts: {len(high_severity)}")
                result["status"] = "FAIL"
            else:
                result["warnings"].append(f"Unresolved MEDIUM conflicts: {len(unresolved)}")

        # Check 5: No false target-end claims
        for mission_id, mission in self.missions.items():
            if mission.target_type == "LINUX_DISTRO":
                build_key = self.get_shared_buffer("os_build_executed")
                if build_key == True:
                    result["failures"].append("OS build false claim detected")
                    result["status"] = "FAIL"

        # Check 6: Source-placeholder labels preserved
        source_mode = self.get_shared_buffer("research_source_mode")
        if source_mode == "SOURCE_PLACEHOLDER":
            result["warnings"].append("Research mode is SOURCE_PLACEHOLDER - live research not claimed")

        # Summary
        if result["status"] == "PASS" and result["warnings"]:
            result["status"] = "WARN"

        result["summary"] = f"{result['status']}: {len(result['warnings'])} warnings, {len(result['failures'])} failures"
        return result

    # === Export ===

    def export_cohort_report(self) -> Dict:
        """Export complete cohort report."""
        return {
            "cohort_id": self.cohort_id,
            "description": self.description,
            "missions": {
                mid: {
                    "mission_id": mid,
                    "target_type": m.target_type,
                    "goal": m.goal,
                    "priority": m.priority,
                    "status": m.status,
                    "blocked_reason": m.blocked_reason,
                    "quality_gates": m.quality_gates,
                    "evidence_ids": m.evidence_ids,
                    "stages": m.stages
                }
                for mid, m in self.missions.items()
            },
            "cross_dependencies": [asdict(d) for d in self.cross_dependencies],
            "shared_evidence": [asdict(e) for e in self.shared_evidence],
            "shared_buffer": {
                k: {
                    "key": v.key,
                    "value": v.value,
                    "source_mission": v.source_mission,
                    "timestamp": v.timestamp,
                    "overwritten": v.overwritten
                }
                for k, v in self.shared_buffer.items()
            },
            "conflicts": [asdict(c) for c in self.conflicts],
            "checkpoints": [
                {
                    "checkpoint_id": cp.checkpoint_id,
                    "label": cp.label,
                    "timestamp": cp.timestamp
                }
                for cp in self.checkpoints
            ],
            "global_quality_gate": self.run_global_quality_gate(),
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }

    def save_state(self, path: str = "") -> str:
        """Save cohort state to file."""
        if not path:
            os.makedirs(COHORT_DIR, exist_ok=True)
            path = f"{COHORT_DIR}/{self.cohort_id}.json"

        with open(path, "w") as f:
            json.dump(self.export_cohort_report(), f, indent=2, default=str)

        return path

    @classmethod
    def load_state(cls, path: str) -> "MultiMissionCoordinator":
        """Load cohort state from file."""
        with open(path) as f:
            data = json.load(f)

        coord = cls(data["cohort_id"], data.get("description", ""))
        coord.created_at = data.get("created_at", datetime.now(timezone.utc).isoformat())
        coord.updated_at = data.get("updated_at", datetime.now(timezone.utc).isoformat())

        # Load missions
        for mid, mdata in data.get("missions", {}).items():
            mission = Mission(
                mission_id=mdata["mission_id"],
                target_type=mdata["target_type"],
                goal=mdata.get("goal", ""),
                priority=mdata.get("priority", "MEDIUM"),
                status=mdata.get("status", "PENDING"),
                blocked_reason=mdata.get("blocked_reason", ""),
                quality_gates=mdata.get("quality_gates", []),
                evidence_ids=mdata.get("evidence_ids", []),
                stages=mdata.get("stages", [])
            )
            coord.missions[mid] = mission

        # Load dependencies
        for dep_data in data.get("cross_dependencies", []):
            dep = CrossDependency(**dep_data)
            coord.cross_dependencies.append(dep)

        # Load evidence
        for ev_data in data.get("shared_evidence", []):
            ev = SharedEvidence(**ev_data)
            coord.shared_evidence.append(ev)

        # Load buffer
        for k, v in data.get("shared_buffer", {}).items():
            entry = SharedBufferEntry(
                key=v["key"],
                value=v["value"],
                source_mission=v["source_mission"],
                timestamp=v["timestamp"],
                overwritten=v.get("overwritten", False)
            )
            coord.shared_buffer[k] = entry

        # Load conflicts
        for c_data in data.get("conflicts", []):
            c = Conflict(**c_data)
            coord.conflicts.append(c)

        return coord


# === CLI for Testing ===

def main():
    """CLI for multi-mission coordinator."""
    import argparse

    parser = argparse.ArgumentParser(description="ILMA Multi-Mission Coordinator")
    sub = parser.add_subparsers(dest="command")

    # Create cohort
    create_p = sub.add_parser("create", help="Create cohort")
    create_p.add_argument("cohort_id", help="Cohort ID")

    # Add mission
    add_p = sub.add_parser("add-mission", help="Add mission")
    add_p.add_argument("cohort_id", help="Cohort ID")
    add_p.add_argument("mission_id", help="Mission ID")
    add_p.add_argument("target_type", help="Target type")
    add_p.add_argument("--priority", default="MEDIUM", help="Priority")

    # Report
    report_p = sub.add_parser("report", help="Export cohort report")
    report_p.add_argument("cohort_id", help="Cohort ID")

    args = parser.parse_args()

    if args.command == "create":
        coord = MultiMissionCoordinator(args.cohort_id)
        path = coord.save_state()
        print(f"Cohort created: {args.cohort_id}")
        print(f"State saved to: {path}")

    elif args.command == "report":
        path = f"{COHORT_DIR}/{args.cohort_id}.json"
        if os.path.exists(path):
            coord = MultiMissionCoordinator.load_state(path)
            report = coord.export_cohort_report()
            print(json.dumps(report, indent=2, default=str))
        else:
            print(f"Cohort {args.cohort_id} not found")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()