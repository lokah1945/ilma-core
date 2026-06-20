#!/usr/bin/env python3
"""
ILMA Ethics Core v1.0
Ethics decision making, violation tracking, and audit trail.
Mimics ILMA's ethics_core.py functionality.
"""
import re
import json
import hashlib
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ViolationLevel(Enum):
    """Violation severity levels."""
    INFO = "info"
    WARNING = "warning"
    VIOLATION = "violation"
    CRITICAL = "critical"
    BLOCK = "block"  # Must block action

@dataclass
class EthicsRule:
    """A single ethics rule."""
    id: str
    name: str
    description: str
    pattern: str  # Regex pattern
    violation_level: ViolationLevel
    action: str  # log, warn, block
    enabled: bool = True
    category: str = "general"

@dataclass
class Violation:
    """A recorded ethics violation."""
    id: str
    rule_id: str
    rule_name: str
    level: ViolationLevel
    message: str
    task: str
    context: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)
    resolved: bool = False
    resolution: Optional[str] = None

class EthicsCore:
    """
    Ethics Core for ILMA - ensures ethical behavior and compliance.
    Provides violation tracking, audit trail, and decision making.
    """
    
    ETHICS_RULES = [
        # Data Privacy
        EthicsRule(
            id="privacy_001",
            name="No Personal Data Exposure",
            description="Do not expose personal data of individuals",
            pattern=r"(?:password|secret|token|api.?key|credential)\s*[=:]\s*[\"\']?[a-zA-Z0-9_-]{8,}",
            violation_level=ViolationLevel.CRITICAL,
            action="block",
            category="privacy"
        ),
        EthicsRule(
            id="privacy_002",
            name="No Social Security Numbers",
            description="Do not process SSN or similar identifiers",
            pattern=r"\b\d{3}[-]?\d{2}[-]?\d{4}\b",
            violation_level=ViolationLevel.CRITICAL,
            action="block",
            category="privacy"
        ),
        
        # Security
        EthicsRule(
            id="security_001",
            name="No Harmful Commands",
            description="Do not execute potentially harmful commands",
            pattern=r"(?:rm\s+-rf\s+/|mkfs|format\s+/:|>:)",
            violation_level=ViolationLevel.BLOCK,
            action="block",
            category="security"
        ),
        EthicsRule(
            id="security_002",
            name="No Privilege Escalation",
            description="Do not attempt unauthorized privilege escalation",
            pattern=r"(?:sudo|chmod|chown).*(?:0|777|root).*(?:without|skip)",
            violation_level=ViolationLevel.VIOLATION,
            action="warn",
            category="security"
        ),
        
        # Content Safety
        EthicsRule(
            id="safety_001",
            name="No Malicious Code",
            description="Do not create malware or malicious code",
            pattern=r"(?:keylogger|trojan|backdoor|rootkit|ransomware)",
            violation_level=ViolationLevel.CRITICAL,
            action="block",
            category="safety"
        ),
        EthicsRule(
            id="safety_002",
            name="No Phishing Content",
            description="Do not create phishing content",
            pattern=r"(?:phishing|fake\s+login|fake\s+bank)",
            violation_level=ViolationLevel.VIOLATION,
            action="warn",
            category="safety"
        ),
        
        # Fairness
        EthicsRule(
            id="fairness_001",
            name="No Discriminatory Language",
            description="Avoid discriminatory or biased language",
            pattern=r"(?:all\s+\w+\s+are|\w+\s+never\s+can|\w+\s+always\s+will)",
            violation_level=ViolationLevel.WARNING,
            action="warn",
            category="fairness"
        ),
        
        # Transparency
        EthicsRule(
            id="transparency_001",
            name="No Hallucination Claims",
            description="Do not present invented facts as truth",
            pattern=r"(?:i\s+am\s+certain\s+that|definitely\s+true|100%\s+accurate)",
            violation_level=ViolationLevel.INFO,
            action="log",
            category="transparency"
        ),
    ]
    
    def __init__(self, storage_file: str = 'memory/ethics.json'):
        self.storage_file = Path(storage_file)
        self.storage_file.parent.mkdir(parents=True, exist_ok=True)
        self.rules: Dict[str, EthicsRule] = {r.id: r for r in self.ETHICS_RULES}
        self.violations: List[Violation] = []
        self.audit_log: List[Dict] = []
        self.load()
    
    def load(self):
        """Load violations and audit log."""
        if self.storage_file.exists():
            try:
                data = json.loads(self.storage_file.read_text())
                self.violations = [Violation(
                    id=v['id'],
                    rule_id=v['rule_id'],
                    rule_name=v['rule_name'],
                    level=ViolationLevel(v['level']),
                    message=v['message'],
                    task=v['task'],
                    context=v.get('context', {}),
                    timestamp=datetime.fromisoformat(v['timestamp']),
                    resolved=v.get('resolved', False),
                    resolution=v.get('resolution')
                ) for v in data.get('violations', [])]
                self.audit_log = data.get('audit_log', [])
            except Exception as e:
                logger.error(f"Error loading ethics data: {e}")
    
    def save(self):
        """Save violations and audit log."""
        data = {
            'violations': [
                {
                    'id': v.id,
                    'rule_id': v.rule_id,
                    'rule_name': v.rule_name,
                    'level': v.level.value,
                    'message': v.message,
                    'task': v.task,
                    'context': v.context,
                    'timestamp': v.timestamp.isoformat(),
                    'resolved': v.resolved,
                    'resolution': v.resolution
                } for v in self.violations[-100:]  # Keep last 100
            ],
            'audit_log': self.audit_log[-500:]  # Keep last 500
        }
        self.storage_file.write_text(json.dumps(data, indent=2))
    
    def check(self, text: str, task: str = "", context: Dict = None) -> List[Violation]:
        """Check text against all ethics rules."""
        violations_found = []
        
        for rule in self.rules.values():
            if not rule.enabled:
                continue
            
            if re.search(rule.pattern, text, re.IGNORECASE):
                violation = Violation(
                    id=hashlib.md5(f"{rule.id}{task}{datetime.now().isoformat()}".encode()).hexdigest()[:12],
                    rule_id=rule.id,
                    rule_name=rule.name,
                    level=rule.violation_level,
                    message=f"Potential ethics issue: {rule.description}",
                    task=task,
                    context=context or {}
                )
                violations_found.append(violation)
                
                if rule.action in ("warn", "block"):
                    self.violations.append(violation)
                    self.log_violation(violation)
        
        return violations_found
    
    def log_violation(self, violation: Violation):
        """Log a violation to audit trail."""
        self.audit_log.append({
            'type': 'violation',
            'violation_id': violation.id,
            'rule_id': violation.rule_id,
            'level': violation.level.value,
            'message': violation.message,
            'task': violation.task[:100],
            'timestamp': violation.timestamp.isoformat()
        })
        self.save()
    
    def log_decision(self, decision: str, task: str, rationale: str, context: Dict = None):
        """Log an ethical decision."""
        self.audit_log.append({
            'type': 'decision',
            'decision': decision,
            'task': task[:100],
            'rationale': rationale,
            'context': context or {},
            'timestamp': datetime.now().isoformat()
        })
        self.save()
    
    def log_escalation(self, issue: str, task: str, reason: str):
        """Log an escalation."""
        self.audit_log.append({
            'type': 'escalation',
            'issue': issue,
            'task': task[:100],
            'reason': reason,
            'timestamp': datetime.now().isoformat()
        })
        self.save()
    
    def should_block(self, violations: List[Violation]) -> bool:
        """Check if any violation should block action."""
        return any(v.level == ViolationLevel.BLOCK for v in violations)
    
    def should_warn(self, violations: List[Violation]) -> bool:
        """Check if any violation should warn."""
        return any(v.level in (ViolationLevel.WARNING, ViolationLevel.VIOLATION, ViolationLevel.CRITICAL) for v in violations)
    
    def resolve_violation(self, violation_id: str, resolution: str):
        """Mark a violation as resolved."""
        for v in self.violations:
            if v.id == violation_id:
                v.resolved = True
                v.resolution = resolution
                self.save()
                return True
        return False
    
    def get_violations(self, level: ViolationLevel = None, unresolved_only: bool = False) -> List[Violation]:
        """Get violations, optionally filtered."""
        result = self.violations
        if level:
            result = [v for v in result if v.level == level]
        if unresolved_only:
            result = [v for v in result if not v.resolved]
        return sorted(result, key=lambda x: x.timestamp, reverse=True)
    
    def get_audit_log(self, limit: int = 100) -> List[Dict]:
        """Get audit log."""
        return sorted(self.audit_log, key=lambda x: x['timestamp'], reverse=True)[:limit]
    
    def add_rule(self, rule: EthicsRule) -> bool:
        """Add a custom ethics rule."""
        if rule.id in self.rules:
            return False
        self.rules[rule.id] = rule
        return True
    
    def enable_rule(self, rule_id: str) -> bool:
        """Enable a rule."""
        if rule_id in self.rules:
            self.rules[rule_id].enabled = True
            return True
        return False
    
    def disable_rule(self, rule_id: str) -> bool:
        """Disable a rule."""
        if rule_id in self.rules:
            self.rules[rule_id].enabled = False
            return True
        return False
    
    def get_stats(self) -> Dict:
        """Get ethics statistics."""
        return {
            'total_violations': len(self.violations),
            'unresolved': sum(1 for v in self.violations if not v.resolved),
            'by_level': {
                level.value: sum(1 for v in self.violations if v.level == level)
                for level in ViolationLevel
            },
            'total_rules': len(self.rules),
            'enabled_rules': sum(1 for r in self.rules.values() if r.enabled),
            'audit_entries': len(self.audit_log)
        }
    
    def health_check(self) -> dict:
        """Health endpoint."""
        return {
            "ok": True,
            "module": "ethics_core",
            "rules": len(self.rules),
            "violations": len(self.violations),
            "audit_entries": len(self.audit_log)
        }

if __name__ == '__main__':
    core = EthicsCore()
    
    print("="*60)
    print("ILMA Ethics Core - Test")
    print("="*60)
    
    # Test checks
    test_texts = [
        "Set password = 'abc123' for user",
        "I am certain that this is 100% accurate",
        "Create a keylogger for security testing",
    ]
    
    for text in test_texts:
        violations = core.check(text, task="Test task")
        if violations:
            for v in violations:
                print(f"\n[!] Violation: {v.rule_name}")
                print(f"    Level: {v.level.value}")
                print(f"    Message: {v.message}")
        else:
            print(f"\n[OK] '{text[:40]}...' - No violations")
    
    print(f"\nStats: {core.get_stats()}")
    print(f"\nHealth: {core.health_check()}")
    print("\n[✅] Ethics Core operational")
