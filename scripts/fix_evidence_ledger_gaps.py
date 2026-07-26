#!/usr/bin/env python3
"""
Fix evidence ledger gaps in ILMA capability registry.

Finds capabilities that have evidence_id but NO corresponding entry in the ledger,
then downgrades them to STRONGLY_SUPPORTED and removes the orphaned evidence_id.

Risk: LOW (downgrade, not false claim)
"""

import json
from pathlib import Path

WORKSPACE = Path("/root/.hermes/profiles/ilma")
REGISTRY_PATH = WORKSPACE / "config" / "ilma_capability_registry.json"
LEDGER_PATH = WORKSPACE / "evidence" / "ilma_evidence_ledger.json"
OUTPUT_PATH = WORKSPACE / "config" / "ilma_capability_registry.json"


def load_json(path):
    with open(path, 'r') as f:
        return json.load(f)


def save_json(path, data):
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)
    print(f"  Saved: {path}")


def main():
    print("=" * 60)
    print("ILMA Evidence Ledger Gap Fix")
    print("=" * 60)
    
    # 1. Load capability registry
    print("\n[1] Loading capability registry...")
    registry = load_json(REGISTRY_PATH)
    capabilities = registry.get("capabilities", {})
    total_caps = len(capabilities)
    print(f"  Total capabilities: {total_caps}")
    
    # 2. Load evidence ledger
    print("\n[2] Loading evidence ledger...")
    ledger = load_json(LEDGER_PATH)
    ledger_entries = ledger.get("entries", [])
    
    # 3. Extract all valid evidence IDs from ledger
    print("\n[3] Extracting valid evidence IDs from ledger...")
    valid_evidence_ids = set()
    for entry in ledger_entries:
        eid = entry.get("evidence_id")
        if eid:
            valid_evidence_ids.add(eid)
    print(f"  Valid evidence IDs in ledger: {len(valid_evidence_ids)}")
    
    # 4. Find capabilities with orphaned evidence_id
    print("\n[4] Finding orphaned evidence_ids...")
    orphaned = []
    for cap_name, cap_data in capabilities.items():
        evidence_id = cap_data.get("evidence_id")
        if evidence_id and evidence_id not in valid_evidence_ids:
            orphaned.append({
                "capability": cap_name,
                "evidence_id": evidence_id,
                "current_status": cap_data.get("status", "UNKNOWN")
            })
    
    print(f"  Orphaned evidence_ids found: {len(orphaned)}")
    
    if not orphaned:
        print("\n✅ No gaps found! All evidence_ids have ledger entries.")
        return
    
    # Show some examples
    print("\n  Examples of orphaned evidence_ids:")
    for item in orphaned[:5]:
        print(f"    - {item['capability']}: {item['evidence_id']} (status: {item['current_status']})")
    if len(orphaned) > 5:
        print(f"    ... and {len(orphaned) - 5} more")
    
    # 5. Downgrade orphaned capabilities
    print("\n[5] Downgrading orphaned capabilities...")
    downgraded_count = 0
    for item in orphaned:
        cap_name = item["capability"]
        cap_data = capabilities[cap_name]
        
        # Downgrade to STRONGLY_SUPPORTED
        cap_data["status"] = "STRONGLY_SUPPORTED"
        
        # Remove orphaned evidence_id
        if "evidence_id" in cap_data:
            del cap_data["evidence_id"]
        
        # Add note about downgrade
        cap_data["evidence_note"] = "Downgraded: evidence_id not in ledger"
        
        downgraded_count += 1
        print(f"  Downgraded: {cap_name}")
    
    print(f"\n  Total downgraded: {downgraded_count}")
    
    # 6. Verify weak_VERIFIED count remains 0
    print("\n[6] Verifying weak_VERIFIED count...")
    weak_verified_count = sum(
        1 for cap in capabilities.values() 
        if cap.get("status") == "weak_VERIFIED"
    )
    print(f"  weak_VERIFIED count: {weak_verified_count}")
    
    if weak_verified_count > 0:
        print("  ⚠️ WARNING: weak_VERIFIED entries exist! Fixing...")
        for cap_name, cap_data in capabilities.items():
            if cap_data.get("status") == "weak_VERIFIED":
                cap_data["status"] = "STRONGLY_SUPPORTED"
                print(f"    Fixed: {cap_name}")
    else:
        print("  ✅ weak_VERIFIED count is 0")
    
    # 7. Save patched registry
    print("\n[7] Saving patched registry...")
    save_json(OUTPUT_PATH, registry)
    
    # 8. Report gap_count
    print("\n[8] Final verification...")
    # Re-check gap count
    gap_count = 0
    for cap_name, cap_data in capabilities.items():
        evidence_id = cap_data.get("evidence_id")
        if evidence_id and evidence_id not in valid_evidence_ids:
            gap_count += 1
    
    print(f"  Gap count after patch: {gap_count}")
    
    if gap_count == 0:
        print("\n✅ SUCCESS: gap_count = 0")
    else:
        print(f"\n❌ FAILED: gap_count = {gap_count}")
    
    print("\n" + "=" * 60)
    print(f"SUMMARY: Downgraded {downgraded_count} capabilities")
    print("=" * 60)
    
    return downgraded_count


if __name__ == "__main__":
    main()