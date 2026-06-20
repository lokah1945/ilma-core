#!/usr/bin/env python3
"""
ILMA Extreme Mission Loop Controller
Phase 39C: Long-run mission orchestration with checkpoint/resume

NOT CLAIMED:
- Real-time execution (this is orchestration only)
- External API integration
- Live provider calls
- Build system or compiler
- Publishing pipeline
- Cloud deployment

API: create_mission, add_stage, add_task, mark_task_status, checkpoint, resume,
     validate_ready_for_next_stage, export_mission_report, list_missions
"""
import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pathlib import Path

# State storage
BASE_DIR = Path("/root/.hermes/profiles/ilma")
STATE_DIR = BASE_DIR / "state" / "missions"
STATE_DIR.mkdir(parents=True, exist_ok=True)

def _get_state_path(mission_id: str) -> Path:
    return STATE_DIR / f"{mission_id}.json"

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

class MissionLoopController:
    """Extreme mission loop controller - orchestrates long-run missions."""
    
    def __init__(self):
        self._missions: Dict[str, Dict] = {}  # In-memory cache
    
    def _load(self, mission_id: str) -> Optional[Dict]:
        """Load mission from disk."""
        path = _get_state_path(mission_id)
        if path.exists():
            with open(path) as f:
                return json.load(f)
        return None
    
    def _save(self, mission: Dict) -> None:
        """Save mission to disk."""
        mission_id = mission['mission_id']
        path = _get_state_path(mission_id)
        with open(path, 'w') as f:
            json.dump(mission, f, indent=2)
        self._missions[mission_id] = mission
    
    def _new_id(self) -> str:
        return str(uuid.uuid4())[:8]
    
    def create_mission(self, goal: str, target_type: str, constraints: Dict = None) -> str:
        """
        Create new mission.
        Returns mission_id.
        """
        if target_type not in ['LONGFORM', 'CODEBASE', 'RESEARCH', 'LINUX_DISTRO', 'GENERAL']:
            raise ValueError(f"Invalid target_type: {target_type}")
        
        mission_id = self._new_id()
        mission = {
            'mission_id': mission_id,
            'goal': goal,
            'target_type': target_type,
            'constraints': constraints or {},
            'status': 'ACTIVE',
            'created_at': _now_iso(),
            'updated_at': _now_iso(),
            'stages': {},      # stage_id -> {objective, dependencies, status}
            'tasks': {},       # task_id -> {stage_id, description, acceptance_criteria, status, evidence_id, created_at, completed_at}
            'dependencies': {},# task_id -> [prerequisite_task_ids]
            'checkpoints': [], # [{id, label, timestamp, stage_states}]
            'evidence_ids': [],
            'sub_agent_reviews': [], # [{reviewer, result, findings, timestamp}]
            'external_sources': [],  # [{url, attribution, date, claim}]
            'risk_log': [],          # [{risk, severity, mitigation}]
            'current_stage': None,
            'completed_stages': [],
        }
        self._save(mission)
        return mission_id
    
    def add_stage(self, mission_id: str, stage_id: str, objective: str,
                  dependencies: List[str] = None) -> bool:
        """
        Add stage to mission.
        Returns True if added.
        """
        mission = self._load(mission_id)
        if not mission:
            raise ValueError(f"Mission not found: {mission_id}")
        
        if stage_id in mission['stages']:
            raise ValueError(f"Stage already exists: {stage_id}")
        
        mission['stages'][stage_id] = {
            'objective': objective,
            'dependencies': dependencies or [],
            'status': 'PENDING',
            'created_at': _now_iso(),
        }
        
        if mission['current_stage'] is None:
            mission['current_stage'] = stage_id
        
        mission['updated_at'] = _now_iso()
        self._save(mission)
        return True
    
    def add_task(self, mission_id: str, stage_id: str, task_id: str,
                 description: str, acceptance_criteria: List[str] = None,
                 dependencies: List[str] = None) -> bool:
        """
        Add task to mission stage.
        Returns True if added.
        """
        mission = self._load(mission_id)
        if not mission:
            raise ValueError(f"Mission not found: {mission_id}")
        
        if stage_id not in mission['stages']:
            raise ValueError(f"Stage not found: {stage_id}")
        
        if task_id in mission['tasks']:
            raise ValueError(f"Task already exists: {task_id}")
        
        # Check dependencies exist
        for dep in (dependencies or []):
            if dep not in mission['tasks']:
                raise ValueError(f"Dependency task not found: {dep}")
        
        mission['tasks'][task_id] = {
            'stage_id': stage_id,
            'description': description,
            'acceptance_criteria': acceptance_criteria or [],
            'status': 'PENDING',
            'evidence_id': None,
            'dependencies': dependencies or [],
            'created_at': _now_iso(),
            'completed_at': None,
        }
        mission['updated_at'] = _now_iso()
        self._save(mission)
        return True
    
    def mark_task_status(self, mission_id: str, task_id: str, status: str,
                         evidence_id: str = None) -> bool:
        """
        Mark task status: PENDING, IN_PROGRESS, COMPLETED, FAILED, BLOCKED
        """
        mission = self._load(mission_id)
        if not mission:
            raise ValueError(f"Mission not found: {mission_id}")
        
        if task_id not in mission['tasks']:
            raise ValueError(f"Task not found: {task_id}")
        
        valid_statuses = ['PENDING', 'IN_PROGRESS', 'COMPLETED', 'FAILED', 'BLOCKED']
        if status not in valid_statuses:
            raise ValueError(f"Invalid status: {status}")
        
        task = mission['tasks'][task_id]
        task['status'] = status
        
        if evidence_id:
            task['evidence_id'] = evidence_id
            if evidence_id not in mission['evidence_ids']:
                mission['evidence_ids'].append(evidence_id)
        
        if status == 'COMPLETED':
            task['completed_at'] = _now_iso()
        
        mission['updated_at'] = _now_iso()
        self._save(mission)
        return True
    
    def checkpoint(self, mission_id: str, label: str) -> str:
        """
        Create checkpoint of current mission state.
        Returns checkpoint_id.
        """
        mission = self._load(mission_id)
        if not mission:
            raise ValueError(f"Mission not found: {mission_id}")
        
        checkpoint_id = self._new_id()
        
        # Capture stage states
        stage_states = {}
        for stage_id, stage in mission['stages'].items():
            stage_states[stage_id] = {
                'status': stage['status'],
                'tasks': {
                    tid: mission['tasks'][tid]['status']
                    for tid in mission['tasks']
                    if mission['tasks'][tid]['stage_id'] == stage_id
                }
            }
        
        checkpoint = {
            'id': checkpoint_id,
            'label': label,
            'timestamp': _now_iso(),
            'stage_states': stage_states,
            'mission_status': mission['status'],
            'current_stage': mission['current_stage'],
        }
        
        mission['checkpoints'].append(checkpoint)
        mission['updated_at'] = _now_iso()
        self._save(mission)
        
        return checkpoint_id
    
    def resume(self, mission_id: str, checkpoint_id: str) -> bool:
        """
        Restore mission to checkpoint state.
        Returns True if restored.
        """
        mission = self._load(mission_id)
        if not mission:
            raise ValueError(f"Mission not found: {mission_id}")
        
        # Find checkpoint
        cp = None
        for c in mission['checkpoints']:
            if c['id'] == checkpoint_id:
                cp = c
                break
        
        if not cp:
            raise ValueError(f"Checkpoint not found: {checkpoint_id}")
        
        # Restore stage statuses
        for stage_id, state in cp['stage_states'].items():
            if stage_id in mission['stages']:
                mission['stages'][stage_id]['status'] = state['status']
                for tid, tstatus in state['tasks'].items():
                    if tid in mission['tasks']:
                        mission['tasks'][tid]['status'] = tstatus
                        mission['tasks'][tid]['completed_at'] = None
        
        mission['status'] = cp['mission_status']
        mission['current_stage'] = cp['current_stage']
        mission['updated_at'] = _now_iso()
        
        # Mark as rolled back
        mission['risk_log'].append({
            'event': 'rollback',
            'checkpoint_id': checkpoint_id,
            'timestamp': _now_iso(),
        })
        
        self._save(mission)
        return True
    
    def validate_ready_for_next_stage(self, mission_id: str, next_stage_id: str) -> Dict:
        """
        Validate all tasks in current stage are complete before advancing.
        Returns {ready: bool, blockers: []}
        """
        mission = self._load(mission_id)
        if not mission:
            raise ValueError(f"Mission not found: {mission_id}")
        
        if next_stage_id not in mission['stages']:
            raise ValueError(f"Stage not found: {next_stage_id}")
        
        # Check stage dependencies
        stage = mission['stages'][next_stage_id]
        for dep in stage.get('dependencies', []):
            if dep not in mission['completed_stages']:
                return {
                    'ready': False,
                    'blockers': [f"Dependency stage not completed: {dep}"],
                    'stage_dependencies': stage.get('dependencies', []),
                    'completed_stages': mission['completed_stages'],
                }
        
        # Check all tasks in current stage are complete
        current = mission['current_stage']
        blockers = []
        
        if current:
            for task_id, task in mission['tasks'].items():
                if task['stage_id'] == current and task['status'] != 'COMPLETED':
                    blockers.append(f"Task incomplete: {task_id} ({task['status']})")
            
            # Check acceptance criteria for each task
            for task_id, task in mission['tasks'].items():
                if task['stage_id'] == current and task['status'] == 'COMPLETED':
                    if not task.get('evidence_id'):
                        blockers.append(f"Task completed without evidence: {task_id}")
        
        return {
            'ready': len(blockers) == 0,
            'blockers': blockers,
            'current_stage': current,
            'next_stage': next_stage_id,
        }
    
    def advance_stage(self, mission_id: str) -> Optional[str]:
        """
        Advance to next stage if ready.
        Returns new current_stage or None if blocked.
        """
        mission = self._load(mission_id)
        if not mission:
            raise ValueError(f"Mission not found: {mission_id}")
        
        current = mission['current_stage']
        
        # Mark current as completed
        if current:
            mission['stages'][current]['status'] = 'COMPLETED'
            mission['completed_stages'].append(current)
        
        # Find next stage
        stage_ids = list(mission['stages'].keys())
        try:
            idx = stage_ids.index(current)
            if idx + 1 < len(stage_ids):
                next_stage = stage_ids[idx + 1]
                mission['current_stage'] = next_stage
                mission['stages'][next_stage]['status'] = 'ACTIVE'
                mission['updated_at'] = _now_iso()
                self._save(mission)
                return next_stage
        except ValueError:
            pass
        
        mission['status'] = 'STAGES_COMPLETE'
        mission['updated_at'] = _now_iso()
        self._save(mission)
        return None
    
    def export_mission_report(self, mission_id: str) -> Dict:
        """
        Export mission report as dict.
        """
        mission = self._load(mission_id)
        if not mission:
            raise ValueError(f"Mission not found: {mission_id}")
        
        # Calculate stats
        total_tasks = len(mission['tasks'])
        completed_tasks = sum(1 for t in mission['tasks'].values() if t['status'] == 'COMPLETED')
        total_stages = len(mission['stages'])
        completed_stages = sum(1 for s in mission['stages'].values() if s['status'] == 'COMPLETED')
        
        return {
            'mission_id': mission['mission_id'],
            'goal': mission['goal'],
            'target_type': mission['target_type'],
            'status': mission['status'],
            'created_at': mission['created_at'],
            'updated_at': mission['updated_at'],
            'progress': {
                'stages': f"{completed_stages}/{total_stages}",
                'tasks': f"{completed_tasks}/{total_tasks}",
                'stage_pct': round(completed_stages / total_stages * 100, 1) if total_stages else 0,
                'task_pct': round(completed_tasks / total_tasks * 100, 1) if total_tasks else 0,
            },
            'current_stage': mission['current_stage'],
            'completed_stages': mission['completed_stages'],
            'checkpoints': [{'id': c['id'], 'label': c['label'], 'timestamp': c['timestamp']} 
                           for c in mission['checkpoints']],
            'evidence_ids': mission['evidence_ids'],
            'sub_agent_reviews': len(mission['sub_agent_reviews']),
            'external_sources': len(mission['external_sources']),
            'risks': len(mission['risk_log']),
        }
    
    def add_sub_agent_review(self, mission_id: str, reviewer: str, result: str,
                             findings: List[str], scope_limitations: str = None) -> bool:
        """Add sub-agent review result."""
        mission = self._load(mission_id)
        if not mission:
            raise ValueError(f"Mission not found: {mission_id}")
        
        review = {
            'reviewer': reviewer,
            'result': result,  # PASS, FAIL, PARTIAL
            'findings': findings,
            'scope_limitations': scope_limitations or '',
            'timestamp': _now_iso(),
        }
        mission['sub_agent_reviews'].append(review)
        mission['updated_at'] = _now_iso()
        self._save(mission)
        return True
    
    def add_external_source(self, mission_id: str, url: str, attribution: str,
                             claim: str, date: str = None) -> bool:
        """Add external learning source."""
        mission = self._load(mission_id)
        if not mission:
            raise ValueError(f"Mission not found: {mission_id}")
        
        source = {
            'url': url,
            'attribution': attribution,
            'claim': claim,
            'date': date or _now_iso(),
        }
        mission['external_sources'].append(source)
        mission['updated_at'] = _now_iso()
        self._save(mission)
        return True
    
    def list_missions(self) -> List[Dict]:
        """List all missions."""
        missions = []
        for path in STATE_DIR.glob("*.json"):
            with open(path) as f:
                m = json.load(f)
                missions.append({
                    'mission_id': m['mission_id'],
                    'goal': m['goal'],
                    'target_type': m['target_type'],
                    'status': m['status'],
                    'created_at': m['created_at'],
                })
        return missions
    
    def get_mission(self, mission_id: str) -> Optional[Dict]:
        """Get full mission data."""
        return self._load(mission_id)


# Module-level singleton
_controller = MissionLoopController()

# Public API
def create_mission(goal: str, target_type: str, constraints: Dict = None) -> str:
    return _controller.create_mission(goal, target_type, constraints)

def add_stage(mission_id: str, stage_id: str, objective: str, dependencies: List[str] = None) -> bool:
    return _controller.add_stage(mission_id, stage_id, objective, dependencies)

def add_task(mission_id: str, stage_id: str, task_id: str, description: str,
             acceptance_criteria: List[str] = None, dependencies: List[str] = None) -> bool:
    return _controller.add_task(mission_id, stage_id, task_id, description, acceptance_criteria, dependencies)

def mark_task_status(mission_id: str, task_id: str, status: str, evidence_id: str = None) -> bool:
    return _controller.mark_task_status(mission_id, task_id, status, evidence_id)

def checkpoint(mission_id: str, label: str) -> str:
    return _controller.checkpoint(mission_id, label)

def resume(mission_id: str, checkpoint_id: str) -> bool:
    return _controller.resume(mission_id, checkpoint_id)

def validate_ready_for_next_stage(mission_id: str, next_stage_id: str) -> Dict:
    return _controller.validate_ready_for_next_stage(mission_id, next_stage_id)

def advance_stage(mission_id: str) -> Optional[str]:
    return _controller.advance_stage(mission_id)

def export_mission_report(mission_id: str) -> Dict:
    return _controller.export_mission_report(mission_id)

def add_sub_agent_review(mission_id: str, reviewer: str, result: str,
                          findings: List[str], scope_limitations: str = None) -> bool:
    return _controller.add_sub_agent_review(mission_id, reviewer, result, findings, scope_limitations)

def add_external_source(mission_id: str, url: str, attribution: str,
                         claim: str, date: str = None) -> bool:
    return _controller.add_external_source(mission_id, url, attribution, claim, date)

def list_missions() -> List[Dict]:
    return _controller.list_missions()

def get_mission(mission_id: str) -> Optional[Dict]:
    return _controller.get_mission(mission_id)

def main():
    """CLI for testing."""
    import sys
    if len(sys.argv) < 2:
        print("Usage: ilma_extreme_mission_loop.py <command> [args]")
        print("Commands: create, list, report <mission_id>")
        sys.exit(1)
    
    cmd = sys.argv[1]
    try:
        if cmd == 'create':
            mission_id = create_mission("Test Mission", "GENERAL")
            print(f"Created: {mission_id}")
            add_stage(mission_id, "S1", "Setup objectives")
            add_task(mission_id, "S1", "T1", "First task", ["Task works"])
            print(f"Added stage and task")
            report = export_mission_report(mission_id)
            print(json.dumps(report, indent=2))
        elif cmd == 'list':
            missions = list_missions()
            print(json.dumps(missions, indent=2))
        elif cmd == 'report' and len(sys.argv) >= 3:
            report = export_mission_report(sys.argv[2])
            print(json.dumps(report, indent=2))
        else:
            print("Unknown command")
            sys.exit(1)
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()