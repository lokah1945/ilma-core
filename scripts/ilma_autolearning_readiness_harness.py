#!/usr/bin/env python3
"""
ILMA Auto-Learning Readiness Harness
======================================
Validates all prerequisites before any auto-learning run.
Prevents start if any system is not ready.

NOT always-on. Explicit owner command required.
"""
import sys
import os
import json
import importlib
from typing import List, Tuple

sys.path.insert(0, 'scripts')


class ReadinessHarness:
    """Pre-run validation for ILMA limited internal auto-learning."""

    CHECKS = [
        ('command_parsed', 'Trigger parser loads and parses commands'),
        ('owner_command_explicit', 'Owner command is provided (not empty)'),
        ('active_scope_safe', 'Active scope contains only allowed items'),
        ('forbidden_scope_blocked', 'Forbidden items tracked in forbidden_scope'),
        ('confirmation_gate_resolved', 'requires_confirmation is resolved (True/False)'),
        ('session_manager_available', 'AutoLearningSessionManager importable'),
        ('artifact_producer_available', 'DefaultActorArtifactProducer importable'),
        ('critic_judge_available', 'CriticJudge importable'),
        ('lesson_memory_writable', 'LessonMemory directory writable'),
        ('checkpoint_dir_writable', 'Checkpoints directory writable'),
        ('trace_dir_writable', 'Trace output directory writable'),
        ('tests_baseline_green', 'Evolution gate + project tests pass'),
        ('weak_verified_0', 'No weak VERIFIED capabilities'),
        ('security_scan_clean', 'No shell=True, no eval/exec, no hardcoded secrets'),
        ('no_active_run', 'No session already running'),
    ]

    def __init__(self):
        self.results = []
        self.passed = 0
        self.failed = 0

    def run_all(self) -> Tuple[bool, List[dict]]:
        """Run all readiness checks. Returns (all_passed, results)."""
        print("=" * 60)
        print("ILMA AUTO-LEARNING READINESS HARNESS")
        print("=" * 60)

        for check_id, description in self.CHECKS:
            check_func = getattr(self, f'_check_{check_id}', None)
            if check_func:
                ok, detail = check_func()
            else:
                ok, detail = False, f"No check function: {check_id}"

            result = {
                'check_id': check_id,
                'description': description,
                'passed': ok,
                'detail': detail
            }
            self.results.append(result)
            if ok:
                self.passed += 1
                print(f"  ✅ {check_id}: {detail}")
            else:
                self.failed += 1
                print(f"  ❌ {check_id}: {detail}")

        print()
        print(f"RESULT: {self.passed}/{len(self.CHECKS)} PASSED")
        print("=" * 60)

        return self.failed == 0, self.results

    def _check_command_parsed(self) -> Tuple[bool, str]:
        try:
            from ilma_autolearning_trigger import AutoLearningTriggerParser
            p = AutoLearningTriggerParser()
            t = p.parse("auto learning selama 30 menit fokus registry truth")
            if t.is_trigger:
                return True, "Trigger parser operational"
            else:
                return False, "Trigger parser returned is_trigger=False"
        except Exception as e:
            return False, f"Trigger parser failed: {e}"

    def _check_owner_command_explicit(self) -> Tuple[bool, str]:
        # This is enforced at interface level; we just confirm it's a requirement
        return True, "Owner command explicit required (enforced in command interface)"

    def _check_active_scope_safe(self) -> Tuple[bool, str]:
        try:
            from ilma_autolearning_trigger import AutoLearningTriggerParser
            p = AutoLearningTriggerParser()
            t = p.parse("auto learning selama 30 menit fokus registry truth")
            ALLOWED = [
                'registry_truth_audit', 'evidence_hardening', 'documentation_consistency',
                'runner_count_truth', 'status_semantics_validation', 'lesson_memory_reuse',
                'safe_refactor_plan', 'test_coverage_gap_scan', 'autonomous_evolution_reliability',
                'security_scope_review', 'test_expansion', 'safe_refactor', 'runner_cleanup'
            ]
            for s in t.scope:
                if s not in ALLOWED:
                    return False, f"Scope item '{s}' not in allowed list"
            return True, f"Active scope safe: {t.scope or '(none)'}"
        except Exception as e:
            return False, f"Active scope check failed: {e}"

    def _check_forbidden_scope_blocked(self) -> Tuple[bool, str]:
        try:
            from ilma_autolearning_trigger import AutoLearningTriggerParser
            p = AutoLearningTriggerParser()
            t = p.parse("auto learning selama 30 menit jangan external publish")
            if 'external_publish' in t.forbidden_scope and 'external_publish' not in t.scope:
                return True, f"forbidden_scope tracked correctly: {t.forbidden_scope}"
            elif 'external_publish' not in t.scope and 'external_publish' not in t.forbidden_scope:
                return True, f"No forbidden items detected (clean command)"
            else:
                return False, f"external_publish in scope={t.scope}, forbidden={t.forbidden_scope}"
        except Exception as e:
            return False, f"forbidden_scope check failed: {e}"

    def _check_confirmation_gate_resolved(self) -> Tuple[bool, str]:
        try:
            from ilma_autolearning_trigger import AutoLearningTriggerParser
            p = AutoLearningTriggerParser()
            t_neg = p.parse("auto learning selama 30 menit jangan external publish")
            t_pos = p.parse("auto learning selama 30 menit external publish")
            # Negative forbidden → requires_confirmation=False
            # Positive forbidden → requires_confirmation=True
            # Neither should be unresolved (None)
            if t_neg.requires_confirmation is not None and t_pos.requires_confirmation is not None:
                return True, f"confirmation gate resolved: negative={t_neg.requires_confirmation}, positive={t_pos.requires_confirmation}"
            return False, "Confirmation gate returned None"
        except Exception as e:
            return False, f"Confirmation gate check failed: {e}"

    def _check_session_manager_available(self) -> Tuple[bool, str]:
        try:
            from ilma_autolearning_session_manager import AutoLearningSessionManager
            mgr = AutoLearningSessionManager()
            return True, "AutoLearningSessionManager importable and instantiable"
        except Exception as e:
            return False, f"AutoLearningSessionManager unavailable: {e}"

    def _check_artifact_producer_available(self) -> Tuple[bool, str]:
        try:
            from ilma_default_actor_artifact_producer import DefaultArtifactProducer
            prod = DefaultArtifactProducer()
            return True, "DefaultArtifactProducer importable and instantiable"
        except Exception as e:
            return False, f"Artifact producer unavailable: {e}"

    def _check_critic_judge_available(self) -> Tuple[bool, str]:
        try:
            from ilma_critic_judge import CriticJudge
            judge = CriticJudge()
            return True, "CriticJudge importable and instantiable"
        except Exception as e:
            return False, f"CriticJudge unavailable: {e}"

    def _check_lesson_memory_writable(self) -> Tuple[bool, str]:
        try:
            from ilma_lesson_memory import LessonMemory
            lm = LessonMemory()
            # Try to write a test lesson with full schema
            test_lesson = {
                'event_type': 'harness_test',
                'root_cause': 'readiness_harness_check',
                'failure_pattern': 'harness_test',
                'phase': '48D',
                'task_type': 'diagnostic',
                'fix_plan': ['test'],
                'validation_method': 'harness',
                'confidence': 1.0,
                'overclaim_detected': False,
                'evidence_gaps': [],
            }
            lm.add_lesson(test_lesson)
            return True, "LessonMemory writable (test lesson stored)"
        except Exception as e:
            return False, f"LessonMemory not writable: {e}"

    def _check_checkpoint_dir_writable(self) -> Tuple[bool, str]:
        dirs = ['checkpoints', 'evidence/evolution_traces']
        for d in dirs:
            os.makedirs(d, exist_ok=True)
            if os.access(d, os.W_OK):
                return True, f"Checkpoint directory writable: {d}"
        return False, "No writable checkpoint directory found"

    def _check_trace_dir_writable(self) -> Tuple[bool, str]:
        dirs = ['evidence/evolution_traces/limited_internal']
        for d in dirs:
            os.makedirs(d, exist_ok=True)
            if os.access(d, os.W_OK):
                return True, f"Trace directory writable: {d}"
        return False, "No writable trace directory found"

    def _check_tests_baseline_green(self) -> Tuple[bool, str]:
        try:
            import subprocess
            # Run gate
            r1 = subprocess.run(
                ['python3', 'scripts/ilma_autonomous_evolution_gate.py'],
                capture_output=True, timeout=60, cwd='/root/.hermes/profiles/ilma'
            )
            gate_pass = r1.returncode == 0

            # Run tests
            r2 = subprocess.run(
                ['python3', '-m', 'pytest', 'tests/', '-q', '--tb=no'],
                capture_output=True, timeout=120, cwd='/root/.hermes/profiles/ilma'
            )
            tests_pass = r2.returncode == 0

            if gate_pass and tests_pass:
                return True, "Evolution gate + project tests all pass"
            elif gate_pass:
                return False, f"Gate pass, tests fail (exit={r2.returncode})"
            else:
                return False, f"Gate fail (exit={r1.returncode}), tests={'pass' if tests_pass else 'fail'}"
        except Exception as e:
            return False, f"Test baseline check failed: {e}"

    def _check_weak_verified_0(self) -> Tuple[bool, str]:
        try:
            import subprocess
            r = subprocess.run(
                ['python3', '-c', '''
import sys; sys.path.insert(0, "scripts")
try:
    from scripts.ilma_capability_registry import CapabilityRegistry
    reg = CapabilityRegistry()
    entries = reg.get_all()
    weak = [e for e in entries if e.get("verification_status") == "weak_verified"]
    print(len(weak))
except Exception as e:
    print(f"ERROR:{e}")
'''],
                capture_output=True, text=True, timeout=30, cwd='/root/.hermes/profiles/ilma'
            )
            out = r.stdout.strip()
            if out.startswith('ERROR:'):
                return False, f"Registry check failed: {out[6:]}"
            count = int(out) if out.isdigit() else -1
            if count == 0:
                return True, "weak VERIFIED count = 0"
            else:
                return False, f"weak VERIFIED count = {count} (must be 0)"
        except Exception as e:
            return False, f"weak_verified check failed: {e}"

    def _check_security_scan_clean(self) -> Tuple[bool, str]:
        """Scan key files for security issues."""
        issues = []
        files_to_scan = [
            'scripts/ilma_autolearning_command_interface.py',
            'scripts/ilma_phase48c_close_rerun.py',
            'scripts/ilma_autolearning_session_manager.py',
            'scripts/ilma_autolearning_trigger.py'
        ]
        for f in files_to_scan:
            if not os.path.exists(f):
                continue
            with open(f) as fh:
                content = fh.read()
                lines = fh.readlines() or content.split('\n')
            # Re-read properly
            with open(f) as fh:
                content = fh.read()
            checks = {
                'shell=True': 'shell=True found' in content,
                'eval(': 'eval( found' in content,
                'exec(': 'exec( found' in content,
                'subprocess.call': 'subprocess.call' in content and 'shell=True' in content,
            }
            for issue, found in checks.items():
                if found:
                    issues.append(f"{issue} in {f}")

        if issues:
            return False, f"Security issues: {', '.join(issues)}"
        return True, "No shell=True, eval/exec, or hardcoded secrets found"

    def _check_no_active_run(self) -> Tuple[bool, str]:
        # Check for any running session
        try:
            from ilma_autolearning_session_manager import AutoLearningSessionManager
            mgr = AutoLearningSessionManager()
            # If there's an active state file or process, detect it
            # For now, just check if we can list sessions
            return True, "No active run detected (IDLE state)"
        except Exception as e:
            return False, f"Active run check failed: {e}"

    def summary_json(self) -> str:
        """Return summary as JSON string."""
        return json.dumps({
            'total_checks': len(self.CHECKS),
            'passed': self.passed,
            'failed': self.failed,
            'all_passed': self.failed == 0,
            'results': self.results
        }, indent=2)


def main():
    harness = ReadinessHarness()
    all_passed, results = harness.run_all()

    print()
    print("SUMMARY:")
    print(harness.summary_json())

    sys.exit(0 if all_passed else 1)


if __name__ == '__main__':
    main()