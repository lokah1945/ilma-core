#!/usr/bin/env python3
"""
ILMA Domain Evaluators
Validates output against domain-specific methodology checklists.
"""
import re
from typing import Dict, Any, List

# Structural detectors (audit 2026-06-20 Q2): match real artifacts, not just keywords.
# A genuine citation/source: URL, [1] ref, "Source:/References", or DOI.
_CITATION_RE = re.compile(r"https?://|\[\d+\]|\bsources?\s*:|\breferences\b|\bdoi:\s*\S|\baccording to\b", re.I)
# A genuine diff/patch: ```diff fence, unified-diff markers, or a git hunk header.
_DIFF_RE = re.compile(r"```\s*diff|^---\s+a/|^\+\+\+\s+b/|^@@ .* @@|^diff --git ", re.M)

class DomainValidator:
    def validate(self, output: str, contract: Any) -> Dict[str, Any]:
        """Base validation"""
        return {"valid": True, "score": 1.0, "missing": []}

class ResearchValidator(DomainValidator):
    def validate(self, output: str, contract: Any) -> Dict[str, Any]:
        out_lower = output.lower()
        missing = []
        # Require an ACTUAL citation/source artifact, not just the word "evidence".
        if not _CITATION_RE.search(output or ""):
            missing.append("evidence_table")
        if "confidence" not in out_lower and "limitat" not in out_lower and "keterbatasan" not in out_lower:
            missing.append("uncertainty_handling")

        valid = len(missing) == 0
        return {"valid": valid, "score": 1.0 if valid else 0.5, "missing": missing, "name": "ResearchValidator"}

class WritingValidator(DomainValidator):
    def validate(self, output: str, contract: Any) -> Dict[str, Any]:
        missing = []
        if "#" not in output:
            missing.append("structure_headers")
        
        valid = len(missing) == 0
        return {"valid": valid, "score": 1.0 if valid else 0.6, "missing": missing, "name": "WritingValidator"}

class CodingValidator(DomainValidator):
    def validate(self, output: str, contract: Any) -> Dict[str, Any]:
        out_lower = output.lower()
        missing = []
        # Require a REAL diff/patch artifact (fenced diff / unified-diff markers / git hunk),
        # not merely the word "diff" appearing in prose.
        if not _DIFF_RE.search(output or ""):
            missing.append("diff_generation")
        if "rollback" not in out_lower and "kembalikan" not in out_lower and "revert" not in out_lower:
            missing.append("rollback_plan")
            
        valid = len(missing) == 0
        return {"valid": valid, "score": 1.0 if valid else 0.4, "missing": missing, "name": "CodingValidator"}

class UIUXValidator(DomainValidator):
    def validate(self, output: str, contract: Any) -> Dict[str, Any]:
        out_lower = output.lower()
        missing = []
        if "accessib" not in out_lower and "aria" not in out_lower and "kontras" not in out_lower:
            missing.append("accessibility")
        if "responsiv" not in out_lower and "mobile" not in out_lower:
            missing.append("responsive_states")
            
        valid = len(missing) == 0
        return {"valid": valid, "score": 1.0 if valid else 0.5, "missing": missing, "name": "UIUXValidator"}

class SecurityValidator(DomainValidator):
    def validate(self, output: str, contract: Any) -> Dict[str, Any]:
        out_lower = output.lower()
        missing = []
        if "authoriz" not in out_lower and "scope" not in out_lower and "izin" not in out_lower:
            missing.append("authorization_scope")
        if "remediat" not in out_lower and "mitigasi" not in out_lower and "perbaikan" not in out_lower:
            missing.append("remediation_plan")
            
        valid = len(missing) == 0
        return {"valid": valid, "score": 1.0 if valid else 0.0, "missing": missing, "name": "SecurityValidator"}

class GeneralValidator(DomainValidator):
    pass

VALIDATORS = {
    "ResearchValidator": ResearchValidator(),
    "WritingValidator": WritingValidator(),
    "CodingValidator": CodingValidator(),
    "UIUXValidator": UIUXValidator(),
    "SecurityValidator": SecurityValidator(),
}

def run_domain_evaluators(output: str, contract: Any) -> Dict[str, Any]:
    """Run all required validators from the contract."""
    results = {}
    all_valid = True
    
    if not contract or not hasattr(contract, "required_validators"):
        return {"valid": True, "score": 1.0, "details": "No specific validators required."}

    for v_name in contract.required_validators:
        val = VALIDATORS.get(v_name, GeneralValidator())
        res = val.validate(output, contract)
        results[v_name] = res
        if not res["valid"]:
            all_valid = False

    return {
        "valid": all_valid,
        "details": results,
        "score": sum(r.get("score", 1.0) for r in results.values()) / max(len(results), 1)
    }
