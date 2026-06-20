# Skill Library Audit: Evidence ID Gap

**Date:** 2026-05-10
**Area:** skill_library, evidence, fabrication

---

## Finding

`skills/ilma-multi-agent/SKILL.md` has:
```
evidence_id: ILMA-EVID-20260510-GEMINI-INTEGRATION-001
```

This evidence ID does NOT exist in `evidence/ilma_evidence_ledger.json`.

Under Judge v4 `fabrication` criterion, this would be flagged as FAIL.

---

## Root Cause

Phase 53-55 evidence backfill only covered `config/ilma_capability_registry.json`, not the skill library's own evidence_id fields.

---

## Current State

- Evidence ledger has 7 entries
- Capability registry has 108 STRONGLY_SUPPORTED (no evidence_id fields)
- Skills have evidence_id fields that are not in ledger

---

## Resolution

Should be fixed in Phase 56 (capability truth audit):
1. Either create ledger entries for skill evidence_ids
2. Or remove evidence_id fields from skills that don't have ledger backing

**Status:** Noted for Phase 56. Not blocking — skills are operational even with orphaned evidence_ids.

---

## Related

- Judge v4 `fabrication` criterion: evidence ID not in ledger = FAIL
- Phase 55 downgraded 108 capabilities to STRONGLY_SUPPORTED for same reason
- `ilma-self-improvement/references/evidence-id-ledger-integrity.md` has prevention rule