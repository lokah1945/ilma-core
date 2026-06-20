#!/usr/bin/env python3
"""
ILMA Domain Evaluators
Validates output against domain-specific methodology checklists.
"""
from typing import Dict, Any, List

class DomainValidator:
    def validate(self, output: str, contract: Any) -> Dict[str, Any]:
        """Base validation"""
        return {"valid": True, "score": 1.0, "missing": []}

class ResearchValidator(DomainValidator):
    def validate(self, output: str, contract: Any) -> Dict[str, Any]:
        out_lower = output.lower()
        missing = []
        if "evidence" not in out_lower and "bukti" not in out_lower and "sumber" not in out_lower:
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
        if "diff" not in out_lower and "```diff" not in out_lower and "patch" not in out_lower:
            missing.append("diff_generation")
        if "rollback" not in out_lower and "kembalikan" not in out_lower:
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
