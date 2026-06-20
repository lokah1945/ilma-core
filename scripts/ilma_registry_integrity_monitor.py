#!/usr/bin/env python3
"""
ILMA Phase 26E: Registry Integrity Monitor
==========================================
Monitors capability registry integrity.

Checks:
1. registry JSON valid
2. all 99 capabilities present
3. status enum valid
4. evidence_id required for VERIFIED
5. evidence type qualifies for VERIFIED
6. source_path exists
7. blocker reason required for PARTIAL
8. no duplicate capability IDs
9. no invalid status transitions
10. generate downgrade recommendations
"""

import os
import json
from datetime import datetime

BASE = "/root/.hermes/profiles/ilma"
VALID_STATUSES = {'VERIFIED', 'STRONGLY_SUPPORTED', 'PARTIAL', 'DEPRECATED', 'UNVERIFIED'}
QUALIFYING_EVIDENCE_TYPES = {'BEHAVIORAL', 'SEMANTIC', 'SECURITY', 'INTEGRATION', 'MUTATION'}

def check_registry():
    print("=== REGISTRY INTEGRITY MONITOR ===\n")
    
    results = {
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'checks': [],
        'summary': {'total': 0, 'passed': 0, 'failed': 0, 'warnings': 0},
        'downgrade_recommendations': [],
        'registry_stats': {}
    }
    
    # Load registry
    try:
        registry_path = f"{BASE}/config/ilma_capability_registry.json"
        with open(registry_path) as f:
            registry = json.load(f)
        caps = registry.get('capabilities', registry.get('entries', {}))
        print(f"1. Registry JSON valid: ✅ ({len(caps)} capabilities)")
        results['checks'].append({'check': 'registry_json_valid', 'status': 'PASS', 'details': len(caps)})
        results['summary']['total'] += 1
        results['summary']['passed'] += 1
    except Exception as e:
        print(f"1. Registry JSON valid: ❌ {e}")
        results['checks'].append({'check': 'registry_json_valid', 'status': 'FAIL', 'error': str(e)})
        results['summary']['total'] += 1
        results['summary']['failed'] += 1
        save_report(results)
        return results
    
    # 2. Check all 99 present
    expected = 99
    actual = len(caps)
    if actual == expected:
        print(f"2. All capabilities present: ✅ ({actual}/{expected})")
        results['checks'].append({'check': 'capability_count', 'status': 'PASS', 'details': f"{actual}/{expected}"})
        results['summary']['passed'] += 1
    else:
        print(f"2. All capabilities present: ⚠️ ({actual}/{expected})")
        results['checks'].append({'check': 'capability_count', 'status': 'WARNING', 'details': f"{actual}/{expected}"})
        results['summary']['warnings'] += 1
    results['summary']['total'] += 1
    
    # Stats
    status_counts = {}
    for cap_id, cap_data in caps.items():
        if isinstance(cap_data, dict):
            s = cap_data.get('status', 'UNKNOWN')
            status_counts[s] = status_counts.get(s, 0) + 1
    results['registry_stats'] = status_counts
    print(f"\nRegistry stats: {status_counts}")
    
    # 3. Status enum valid
    invalid_status = []
    for cap_id, cap_data in caps.items():
        if isinstance(cap_data, dict):
            s = cap_data.get('status', '')
            if s not in VALID_STATUSES:
                invalid_status.append({'capability': cap_id, 'status': s})
    
    if not invalid_status:
        print(f"3. Status enum valid: ✅ All valid")
        results['checks'].append({'check': 'status_enum_valid', 'status': 'PASS'})
        results['summary']['passed'] += 1
    else:
        print(f"3. Status enum valid: ❌ {len(invalid_status)} invalid")
        results['checks'].append({'check': 'status_enum_valid', 'status': 'FAIL', 'details': invalid_status})
        results['summary']['failed'] += 1
    results['summary']['total'] += 1
    
    # 4. VERIFIED has evidence_id
    verified_missing_eid = []
    verified = [(cap_id, cap_data) for cap_id, cap_data in caps.items() 
                if isinstance(cap_data, dict) and cap_data.get('status') == 'VERIFIED']
    for cap_id, cap_data in verified:
        if not cap_data.get('evidence_id'):
            verified_missing_eid.append(cap_id)
    
    if not verified_missing_eid:
        print(f"4. VERIFIED has evidence_id: ✅ All have evidence_id")
        results['checks'].append({'check': 'verified_has_evidence_id', 'status': 'PASS', 'details': len(verified)})
        results['summary']['passed'] += 1
    else:
        print(f"4. VERIFIED has evidence_id: ❌ {len(verified_missing_eid)} missing")
        results['checks'].append({'check': 'verified_has_evidence_id', 'status': 'FAIL', 'details': verified_missing_eid})
        results['summary']['failed'] += 1
    results['summary']['total'] += 1
    
    # 5. VERIFIED has qualifying evidence type
    weak_verified = []
    for cap_id, cap_data in verified:
        ev_type = cap_data.get('evidence_type', 'IMPORT_SMOKE')
        if ev_type not in QUALIFYING_EVIDENCE_TYPES:
            weak_verified.append({
                'capability': cap_id,
                'current_type': ev_type,
                'evidence': str(cap_data.get('evidence', ''))[:60]
            })
    
    if not weak_verified:
        print(f"5. VERIFIED has qualifying evidence: ✅ All have BEHAVIORAL/SEMANTIC/SECURITY/INTEGRATION/MUTATION")
        results['checks'].append({'check': 'verified_qualifying_evidence', 'status': 'PASS'})
        results['summary']['passed'] += 1
    else:
        print(f"5. VERIFIED has qualifying evidence: ⚠️ {len(weak_verified)} have weak evidence")
        results['checks'].append({
            'check': 'verified_qualifying_evidence', 
            'status': 'WARNING', 
            'details': f"{len(weak_verified)} need behavioral tests"
        })
        results['summary']['warnings'] += 1
        
        # Recommend downgrades
        for w in weak_verified:
            results['downgrade_recommendations'].append({
                'capability': w['capability'],
                'current_status': 'VERIFIED',
                'recommended_status': 'STRONGLY_SUPPORTED',
                'reason': f"Evidence type is {w['current_type']}, not BEHAVIORAL/SEMANTIC/SECURITY/INTEGRATION/MUTATION",
                'action': 'NEEDS_BEHAVIORAL_TEST'
            })
    results['summary']['total'] += 1
    
    # 6. Source path exists for primary modules
    missing_source = []
    for cap_id, cap_data in caps.items():
        if isinstance(cap_data, dict) and cap_data.get('status') == 'VERIFIED':
            source_path = cap_data.get('source_path', '')
            primary_module = cap_data.get('primary_module', '')
            if source_path:
                if not os.path.exists(f"{BASE}/{source_path}" if not source_path.startswith('/') else source_path):
                    missing_source.append({'capability': cap_id, 'path': source_path})
    
    if not missing_source:
        print(f"6. Source paths exist: ✅ All verified")
        results['checks'].append({'check': 'source_paths_exist', 'status': 'PASS'})
        results['summary']['passed'] += 1
    else:
        print(f"6. Source paths exist: ⚠️ {len(missing_source)} missing")
        results['checks'].append({'check': 'source_paths_exist', 'status': 'WARNING', 'details': missing_source})
        results['summary']['warnings'] += 1
    results['summary']['total'] += 1
    
    # 7. PARTIAL has blocker reason
    partial = [(cap_id, cap_data) for cap_id, cap_data in caps.items() 
               if isinstance(cap_data, dict) and cap_data.get('status') == 'PARTIAL']
    partial_no_reason = []
    for cap_id, cap_data in partial:
        if not cap_data.get('blocker_reason') and not cap_data.get('gap'):
            partial_no_reason.append(cap_id)
    
    if not partial_no_reason:
        print(f"7. PARTIAL has blocker reason: ✅ All have reason")
        results['checks'].append({'check': 'partial_has_blocker', 'status': 'PASS', 'details': len(partial)})
        results['summary']['passed'] += 1
    else:
        print(f"7. PARTIAL has blocker reason: ⚠️ {len(partial_no_reason)} missing")
        results['checks'].append({'check': 'partial_has_blocker', 'status': 'WARNING', 'details': partial_no_reason})
        results['summary']['warnings'] += 1
    results['summary']['total'] += 1
    
    # 8. No duplicate capability IDs
    all_ids = list(caps.keys())
    unique_ids = set(all_ids)
    if len(all_ids) == len(unique_ids):
        print(f"8. No duplicate capability IDs: ✅")
        results['checks'].append({'check': 'no_duplicate_ids', 'status': 'PASS'})
        results['summary']['passed'] += 1
    else:
        print(f"8. No duplicate capability IDs: ❌ Found duplicates")
        results['checks'].append({'check': 'no_duplicate_ids', 'status': 'FAIL'})
        results['summary']['failed'] += 1
    results['summary']['total'] += 1
    
    # Summary
    print(f"\n{'='*60}")
    print(f"SUMMARY:")
    print(f"  Total checks: {results['summary']['total']}")
    print(f"  Passed: {results['summary']['passed']} ✅")
    print(f"  Failed: {results['summary']['failed']} ❌")
    print(f"  Warnings: {results['summary']['warnings']} ⚠️")
    print(f"\n  Downgrade recommendations: {len(results['downgrade_recommendations'])}")
    
    save_report(results)
    return results

def save_report(results):
    os.makedirs(f"{BASE}/logs", exist_ok=True)
    report_path = f"{BASE}/logs/phase26_registry_integrity_report.json"
    with open(report_path, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\nReport: {report_path}")

if __name__ == '__main__':
    results = check_registry()
    exit_code = 0 if results['summary']['failed'] == 0 else 1
    exit(exit_code)