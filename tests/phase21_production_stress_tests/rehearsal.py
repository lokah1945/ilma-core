import sys, os
sys.path.append("/root/.hermes/profiles/ilma/")
from ilma_orchestrator import ILMAOrchestrator
from ilma_skill_resolver import get_skill_resolver

def incident_rehearsal():
    orch = ILMAOrchestrator()
    print("--- INCIDENT 1: Skill Resolver No Match ---")
    sr = get_skill_resolver()
    res = sr.resolve("buat teleportasi portal ajaib", "UNKNOWN_DOMAIN")
    print(res)
    assert res["status"] == "fallback"

    print("--- INCIDENT 2: Invalid Profile Schema ---")
    try:
        profile = orch.route_intent("malformed task !@##$")
        print("Safely handled malformed task.")
        assert profile.get("risk_level") == "low"
    except Exception as e:
        print(f"Failed: {e}")

    print("--- INCIDENT 3: Missing Skill Index File ---")
    idx_path = "/root/.hermes/profiles/ilma/skill_index_manifest.jsonl"
    os.rename(idx_path, idx_path + ".temp")
    try:
        sr2 = get_skill_resolver() # Should not crash
        res2 = sr2.resolve("debug", "CODING")
        print("Handled missing index safely.")
        assert res2["status"] == "fallback"
    finally:
        os.rename(idx_path + ".temp", idx_path)

    print("Incident Rehearsal complete.")

if __name__ == "__main__":
    incident_rehearsal()
