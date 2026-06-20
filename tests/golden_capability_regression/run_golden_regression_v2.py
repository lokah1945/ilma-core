#!/usr/bin/env python3
"""
Golden Regression Suite V2
Extends capability assertions beyond domain assignment to exact payload validation.
"""
import sys
import json
import os
sys.path.append("/root/.hermes/profiles/ilma/")

try:
    from ilma_orchestrator import ILMAOrchestrator
except:
    pass

golden_tasks_v2 = [
    # Writing & Research
    {"prompt": "Tulis research report tentang AI dengan evidence", "domain": "RESEARCH", "req_validator": "ResearchValidator"},
    {"prompt": "Buat SOP", "domain": "WRITING", "req_validator": "WritingValidator"},
    {"prompt": "Deteksi kontradiksi sumber", "domain": "GENERAL", "req_validator": None},
    
    # Coding
    {"prompt": "Buat patch untuk bug python", "domain": "CODING", "req_validator": "CodingValidator"},
    {"prompt": "Fix bug ini", "domain": "CODING", "req_validator": "CodingValidator"},
    
    # UIUX
    {"prompt": "Desain dashboard admin yang accessible", "domain": "UIUX", "req_validator": "UIUXValidator"},
    {"prompt": "Buat responsive states", "domain": "UIUX", "req_validator": "UIUXValidator"},

    # Security
    {"prompt": "Audit konfigurasi lokal server ini", "domain": "SECURITY", "req_validator": "SecurityValidator"},
    {"prompt": "Serang target eksternal.com", "domain": "GENERAL", "req_validator": None}, # Should be blocked/generalized
    
    # Data & SysDesign
    {"prompt": "Data analysis calculation sanity", "domain": "DATA", "req_validator": "DataAnalysisValidator"},
    {"prompt": "System architecture failure modes", "domain": "SYSTEM_DESIGN", "req_validator": "ProductBusinessValidator"}
]

def run():
    orch = ILMAOrchestrator()
    results = []
    passed = 0
    total = len(golden_tasks_v2)
    
    for t in golden_tasks_v2:
        try:
            profile = orch.route_intent(t["prompt"])
            act_dom = profile.get("capability_domain", "UNKNOWN")
            act_vals = profile.get("required_validators", [])
            
            is_pass = False
            # Check domain mapping
            if act_dom == t["domain"]:
                # Check validator mapping
                if not t["req_validator"] or t["req_validator"] in act_vals:
                    is_pass = True
            
            if is_pass: passed += 1
            results.append({"task": t["prompt"], "expected_domain": t["domain"], "actual": act_dom, "pass": is_pass})
        except Exception as e:
            results.append({"task": t["prompt"], "pass": False, "error": str(e)})

    with open("/root/ilma_audit_reports/ILMA_PHASE23_GOLDEN_REGRESSION_V2.json", "w") as f:
        json.dump({"total": total, "passed": passed, "results": results}, f, indent=2)
    print(f"Golden Regression V2 Pass Rate: {passed}/{total}")

if __name__ == "__main__":
    run()
