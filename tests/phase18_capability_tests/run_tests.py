import json
import sys
import os

sys.path.append("/root/.hermes/profiles/ilma/")

try:
    from ilma_orchestrator import ILMAOrchestrator
except ImportError:
    print("FATAL: Cannot import ILMAOrchestrator")
    sys.exit(1)

test_cases = [
    {"id": "writing", "prompt": "Tulis laporan riset berbasis bukti tentang manfaat dan risiko AI agent untuk bisnis."},
    {"id": "coding", "prompt": "debug kode python ini dan berikan patch file nya."},
    {"id": "uiux", "prompt": "Buat UI dashboard analytics untuk admin beserta accessibility report."},
    {"id": "security", "prompt": "Audit konfigurasi lokal ini untuk vulnerabilities dan beri remediation."},
    {"id": "research", "prompt": "Cari data perbandingan sumber AI dan buat evidence table."}
]

def run_tests():
    orch = ILMAOrchestrator()
    results = []
    for tc in test_cases:
        print(f"Running test: {tc['id']} ...")
        # Route Intent Phase
        try:
            profile = orch.route_intent(tc["prompt"])
        except Exception as e:
            profile = {"error": str(e)}
        
        # Execute Intent Phase (dry run mapped via model selection conceptually)
        # Note: we intercept the execution to not burn real tokens in deep audit tests.
        domain = profile.get("capability_domain", "UNKNOWN")
        results.append({
            "test_id": tc["id"],
            "input": tc["prompt"],
            "profile": profile,
            "domain": domain
        })
        
    with open("/root/ilma_audit_reports/ILMA_PHASE18_CAPABILITY_TEST_RESULTS.json", "w") as f:
        json.dump(results, f, indent=2)

if __name__ == "__main__":
    run_tests()
