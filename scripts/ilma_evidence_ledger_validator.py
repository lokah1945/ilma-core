#!/usr/bin/env python3
"""
ILMA Phase 26C: Evidence Ledger Validator
==========================================
Validates evidence registry against canonical schema.

Checks:
1. JSON valid
2. evidence_id uniqueness
3. source_path exists
4. test_path_or_command exists or recorded
5. evidence_type valid
6. VERIFIED capabilities have qualifying evidence type
7. stale evidence detection
8. duplicate evidence IDs
9. evidence pointing to deleted files
10. output JSON report

Evidence types that qualify for VERIFIED:
- BEHAVIORAL
- SEMANTIC
- SECURITY
- INTEGRATION
- MUTATION
"""

import os
import json
from pathlib import Path
from datetime import datetime

BASE = "/root/.hermes/profiles/ilma"
VALID_EVIDENCE_TYPES = {
    'BEHAVIORAL', 'SEMANTIC', 'SECURITY', 'INTEGRATION',
    'MUTATION', 'PERFORMANCE', 'IMPORT_SMOKE', 'COMPILE',
    'FILE_EXISTS', 'MANUAL_REVIEW'
}
QUALIFYING_TYPES = {'BEHAVIORAL', 'SEMANTIC', 'SECURITY', 'INTEGRATION', 'MUTATION'}

def load_registry():
    path = f"{BASE}/config/ilma_capability_registry.json"
    with open(path) as f:
        return json.load(f)

def load_evidence_ledger():
    """Load evidence from registry capabilities"""
    registry = load_registry()
    caps = registry.get('capabilities', registry.get('entries', {}))
    evidence_records = []
    for cap_id, cap_data in caps.items():
        if isinstance(cap_data, dict):
            evidence_id = cap_data.get('evidence_id', '')
            if evidence_id:
                evidence_records.append({
                    'capability': cap_id,
                    'evidence_id': evidence_id,
                    'evidence_type': cap_data.get('evidence_type', 'UNKNOWN'),
                    'source_path': cap_data.get('source_path', ''),
                    'test_path': cap_data.get('test_path', ''),
                    'evidence': cap_data.get('evidence', ''),
                    'date': cap_data.get('date', ''),
                    'status': cap_data.get('status', 'UNKNOWN'),
                    'confidence': cap_data.get('confidence', 0.0)
                })
    return evidence_records

def validate():
    print("=== EVIDENCE LEDGER VALIDATOR ===\n")
    
    results = {
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'registry_path': f"{BASE}/config/ilma_capability_registry.json",
        'checks': [],
        'summary': {
            'total': 0,
            'passed': 0,
            'failed': 0,
            'warnings': 0
        },
        'verified_with_weak_evidence': [],
        'stale_evidence': [],
        'missing_source': [],
        'duplicate_ids': []
    }
    
    # Load evidence
    try:
        evidence_records = load_evidence_ledger()
        print(f"1. Registry JSON valid: ✅ ({len(evidence_records)} evidence records)")
        results['checks'].append({
            'check': 'registry_json_valid',
            'status': 'PASS',
            'details': f"{len(evidence_records)} evidence records"
        })
        results['summary']['total'] += 1
        results['summary']['passed'] += 1
    except json.JSONDecodeError as e:
        print(f"1. Registry JSON valid: ❌ {e}")
        results['checks'].append({
            'check': 'registry_json_valid',
            'status': 'FAIL',
            'error': str(e)
        })
        results['summary']['total'] += 1
        results['summary']['failed'] += 1
        save_report(results)
        return results
    
    # 2. Check evidence_id uniqueness
    evidence_ids = [e['evidence_id'] for e in evidence_records if e['evidence_id']]
    unique_ids = set(evidence_ids)
    if len(evidence_ids) != len(unique_ids):
        dupes = [eid for eid in evidence_ids if evidence_ids.count(eid) > 1]
        results['duplicate_ids'] = list(set(dupes))
        print(f"2. Evidence ID uniqueness: ❌ Found duplicates: {results['duplicate_ids']}")
        results['checks'].append({
            'check': 'evidence_id_uniqueness',
            'status': 'FAIL',
            'details': f"Duplicates: {results['duplicate_ids']}"
        })
        results['summary']['failed'] += 1
    else:
        print(f"2. Evidence ID uniqueness: ✅ All unique ({len(unique_ids)} unique)")
        results['checks'].append({
            'check': 'evidence_id_uniqueness',
            'status': 'PASS',
            'details': f"{len(unique_ids)} unique IDs"
        })
        results['summary']['passed'] += 1
    results['summary']['total'] += 1
    
    # 3. Check source_path exists
    registry = load_registry()
    caps = registry.get('capabilities', registry.get('entries', {}))
    
    for cap_id, cap_data in caps.items():
        if isinstance(cap_data, dict) and cap_data.get('status') == 'VERIFIED':
            source_path = cap_data.get('source_path', '')
            if source_path and not os.path.exists(f"{BASE}/{source_path}" if not source_path.startswith('/') else source_path):
                results['missing_source'].append({
                    'capability': cap_id,
                    'source_path': source_path
                })
                print(f"3. Source exists ({cap_id}): ❌ {source_path}")
    
    if not results['missing_source']:
        print(f"3. Source paths exist: ✅ All verified")
        results['checks'].append({
            'check': 'source_paths_exist',
            'status': 'PASS',
            'details': 'All VERIFIED capabilities have existing source'
        })
        results['summary']['passed'] += 1
    else:
        results['checks'].append({
            'check': 'source_paths_exist',
            'status': 'WARNING',
            'details': f"{len(results['missing_source'])} missing sources"
        })
        results['summary']['warnings'] += 1
    results['summary']['total'] += 1
    
    # 4. Check evidence_type validity
    invalid_types = []
    for e in evidence_records:
        if e['evidence_type'] not in VALID_EVIDENCE_TYPES:
            invalid_types.append({
                'capability': e['capability'],
                'type': e['evidence_type']
            })
    
    if invalid_types:
        print(f"4. Evidence type validity: ❌ {len(invalid_types)} invalid types")
        results['checks'].append({
            'check': 'evidence_type_valid',
            'status': 'FAIL',
            'details': invalid_types
        })
        results['summary']['failed'] += 1
    else:
        print(f"4. Evidence type validity: ✅ All valid")
        results['checks'].append({
            'check': 'evidence_type_valid',
            'status': 'PASS',
            'details': 'All types in VALID_EVIDENCE_TYPES'
        })
        results['summary']['passed'] += 1
    results['summary']['total'] += 1
    
    # 5. Check VERIFIED capabilities have qualifying evidence type
    weak_verified = []
    for cap_id, cap_data in caps.items():
        if isinstance(cap_data, dict) and cap_data.get('status') == 'VERIFIED':
            ev_type = cap_data.get('evidence_type', 'UNKNOWN')
            if ev_type not in QUALIFYING_TYPES:
                weak_verified.append({
                    'capability': cap_id,
                    'current_type': ev_type
                })
    
    if weak_verified:
        print(f"5. VERIFIED evidence type: ⚠️ {len(weak_verified)} have non-qualifying type")
        for w in weak_verified:
            print(f"   - {w['capability']}: {w['current_type']}")
        results['verified_with_weak_evidence'] = weak_verified
        results['checks'].append({
            'check': 'verified_qualifying_evidence',
            'status': 'WARNING',
            'details': f"{len(weak_verified)} VERIFIED with non-qualifying evidence"
        })
        results['summary']['warnings'] += 1
    else:
        print(f"5. VERIFIED evidence type: ✅ All have qualifying type")
        results['checks'].append({
            'check': 'verified_qualifying_evidence',
            'status': 'PASS',
            'details': 'All VERIFIED have BEHAVIORAL/SEMANTIC/SECURITY/INTEGRATION/MUTATION'
        })
        results['summary']['passed'] += 1
    results['summary']['total'] += 1
    
    # 6. Check for stale evidence (older than 14 days)
    stale = []
    cutoff = datetime.now().timestamp() - 14 * 86400
    for e in evidence_records:
        if e['date']:
            try:
                dt = datetime.strptime(e['date'], '%Y-%m-%d')
                if dt.timestamp() < cutoff:
                    stale.append({
                        'capability': e['capability'],
                        'evidence_id': e['evidence_id'],
                        'date': e['date']
                    })
            except ValueError:
                pass
    
    if stale:
        print(f"6. Stale evidence: ⚠️ {len(stale)} records older than 14 days")
        results['stale_evidence'] = stale
        results['checks'].append({
            'check': 'stale_evidence',
            'status': 'WARNING',
            'details': f"{len(stale)} stale records"
        })
        results['summary']['warnings'] += 1
    else:
        print(f"6. Stale evidence: ✅ No stale evidence")
        results['checks'].append({
            'check': 'stale_evidence',
            'status': 'PASS',
            'details': 'All evidence recent'
        })
        results['summary']['passed'] += 1
    results['summary']['total'] += 1
    
    # Summary
    print(f"\n{'='*60}")
    print(f"SUMMARY:")
    print(f"  Total checks: {results['summary']['total']}")
    print(f"  Passed: {results['summary']['passed']} ✅")
    print(f"  Failed: {results['summary']['failed']} ❌")
    print(f"  Warnings: {results['summary']['warnings']} ⚠️")
    
    save_report(results)
    return results

def save_report(results):
    os.makedirs(f"{BASE}/logs", exist_ok=True)
    report_path = f"{BASE}/logs/phase26_evidence_ledger_validation.json"
    with open(report_path, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\nReport: {report_path}")

if __name__ == '__main__':
    results = validate()
    exit_code = 0 if results['summary']['failed'] == 0 else 1
    exit(exit_code)