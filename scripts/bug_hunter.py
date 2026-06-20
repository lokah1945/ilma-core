#!/usr/bin/env python3
"""
bug_hunter.py — Autonomous Bug Hunter & Solver for ILMA
=========================================================
Mission: detect, diagnose, fix, verify, LEARN, EVOLVE.

Subcommands:
  scan        — proactive anomaly + pattern scan dalam scope
  diagnose    — given error msg/file, return root cause + plan
  fix         — apply patch untuk known bug_id
  learn       — append event ke ledger (manual atau auto)
  evolve      — heuristic + playbook promotion cycle
  list        — list bug ledger
  stats       — bug distribution, MTTR, top categories
  playbook    — top fix patterns ( экспорт Markdown)
  init        — initialize/reset ledger + heuristic db
  verify      — re-run regression test untuk bug_id

Persistent state:
  ~/.hermes/profiles/ilma/bug_ledger.jsonl
  ~/.hermes/profiles/ilma/bug_hunter_heuristics.json

Author: ILMA, 2026-06-21 (Bos Huda Choirul Anam).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess  # noqa: F401 — imported for run_judge_verify
import sys
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Paths & constants
# ---------------------------------------------------------------------------

PROFILE_ROOT = Path(os.environ.get("ILMA_PROFILE_ROOT", Path.home() / ".hermes" / "profiles" / "ilma"))
BUG_LEDGER = PROFILE_ROOT / "bug_ledger.jsonl"
HEURISTIC_DB = PROFILE_ROOT / "bug_hunter_heuristics.json"
EVIDENCE_DIR = PROFILE_ROOT / "evidence_ledger"
EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)

# v1.3 — Evidence ledger (real registry path used by ilma_evidence_validator.py)
EVIDENCE_REGISTRY_FILE = PROFILE_ROOT / "ilma_evidence_registry.json"
# Two paths co-exist: validator expects this one
EVIDENCE_LEDGER_FILE = PROFILE_ROOT / "evidence" / "ilma_evidence_ledger.json"

# v1.3 — Evidence ID format kebetulan sama dengan validator: ILMA-EVID-YYYYMMDD-PHASE-CAP-NNN
EVIDENCE_ID_PATTERN = re.compile(
    r"^[IE]L?MA-EVID-\d{8}-[A-Z0-9_]+-[A-Z0-9_]+-\d{3}$"
)
# More permissive on legacy:
LEGACY_EVID_PATTERN = re.compile(r"^[IE]VID-[A-Z0-9-]+$")


def make_evidence_id(capability: str = "BUGHUNTER", seq: int = 1) -> str:
    """
    Format: ILMA-EVID-YYYYMMDD-PHASE-CAPABILITY-NNN
    Phase 'AUTO' untuk ad-hoc.
    """
    dt = datetime.now().strftime("%Y%m%d")
    cap = (capability or "BUGHUNTER").upper().replace("-", "_")[:24]
    return f"ILMA-EVID-{dt}-AUTO-{cap}-{seq:03d}"


def emit_evidence(
    bug_id: str,
    *,
    capability: str = "BUGHUNTER",
    status: str = "ok",
    description: str = "",
    extra: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    """
    Append evidence ke dua ledger (validator-compatible legacy + new BUGHUNTER slot).

    Returns evidence_id on success, None on failure.
    """
    if not EVIDENCE_LEDGER_FILE.parent.exists():
        return None
    try:
        seq = 1
        if EVIDENCE_LEDGER_FILE.exists():
            try:
                data = json.loads(EVIDENCE_LEDGER_FILE.read_text(encoding="utf-8"))
                seq = sum(1 for e in data if e.get("action", "").endswith("bughunter")) + 1
            except (json.JSONDecodeError, OSError):
                seq = 1
        evid = make_evidence_id(capability=capability, seq=seq)
        record = {
            "evidence_id": evid,
            "step": "verify",
            "action": f"bug_hunter+{bug_id}",
            "input_hash": hashlib_md5(bug_id + description),
            "output_hash": hashlib_md5(status + str(extra or {})),
            "timestamp": now_utc_iso(),
            "status": status,
            "metadata": {
                "task_class": "bug_hunter",
                "confidence": 0.9 if status == "ok" else 0.4,
                "bug_id": bug_id,
                "capability": capability,
                "description": description[:200],
                **(extra or {}),
            },
        }
        try:
            existing = json.loads(EVIDENCE_LEDGER_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, FileNotFoundError):
            existing = []
        existing.append(record)
        EVIDENCE_LEDGER_FILE.write_text(json.dumps(existing, indent=2, ensure_ascii=False), encoding="utf-8")
        return evid
    except Exception:
        return None


def hashlib_md5(payload: str) -> str:
    import hashlib
    return hashlib.md5(payload.encode("utf-8")).hexdigest()[:16]


# v1.2 — Chat pattern trigger detector: regex over user/assistant text
CHAT_TRIGGER_PATTERNS: List[Tuple[re.Pattern, str, str, str]] = [
    (re.compile(r"\bTraceback \(most recent call last\)", re.MULTILINE), "stack_trace", "MEDIUM", "Stack trace detected — auto-detect root cause"),
    (re.compile(r"Error:\s*\S+", re.MULTILINE), "error_msg", "MEDIUM", "Generic error string present"),
    (re.compile(r"[Cc]annot find (module|package)", re.MULTILINE), "missing_module", "MEDIUM", "Module not found"),
    (re.compile(r"port \d+.*already in use", re.MULTILINE), "port_collide", "HIGH", "Port conflict"),
    (re.compile(r"EAI_FAIL|NXDOMAIN", re.MULTILINE), "dns_fail", "LOW", "DNS failure"),
    (re.compile(r"OOM|out of memory", re.IGNORECASE), "oom", "HIGH", "Memory exhaustion"),
]


def detect_chat_triggers(text: str) -> List[Dict[str, str]]:
    """Return list of {signature, severity, summary} untuk matching patterns."""
    out = []
    if not text:
        return out
    for pat, sig, sev, summary in CHAT_TRIGGER_PATTERNS:
        if pat.search(text):
            out.append({"signature": sig, "severity": sev, "summary": summary})
    return out


# v1.1 — Judge system verification hook
def run_judge_verify(file: Optional[str] = None, task: str = "bug-hunter self-verify") -> Dict[str, Any]:
    """
    Memanggil `ilma_judge_system.py {quick|verify|full}` dan return aggregated result.
    Falls back gracefully kalau tidak ada file atau judge binary tidak tersedia.
    """
    judge_script = PROFILE_ROOT / "ilma_judge_system.py"
    if not judge_script.exists() or not file:
        return {"ok": False, "skipped": True, "reason": "no judge_binary or no file"}
    if not os.path.isfile(file):
        return {"ok": False, "skipped": True, "reason": f"file not found: {file}"}
    try:
        result = subprocess.run(
            ["python3", str(judge_script), "quick", file, "--task", task, "--json"],
            capture_output=True, text=True, timeout=120,
        )
        out = result.stdout.strip()
        if not out:
            return {"ok": False, "skipped": True, "reason": "judge returned empty", "stderr": result.stderr[:400]}
        try:
            payload = json.loads(out)
            return {"ok": True, "judge_payload": payload, "exit_code": result.returncode}
        except json.JSONDecodeError:
            return {"ok": False, "skipped": True, "reason": "judge returned non-JSON", "raw_excerpt": out[:400]}
    except subprocess.TimeoutExpired:
        return {"ok": False, "skipped": True, "reason": "judge timeout (120s)"}
    except Exception as e:
        return {"ok": False, "skipped": True, "reason": f"judge exception: {e}"}

# Built-in heuristic signatures — seeded dengan pola-pola umum.
# Akan bertambah seiring `learn` + `evolve` cycle.
SEED_HEURISTICS: List[Dict[str, Any]] = [
    {
        "signature": r"old_text is required for '.+' action",
        "category": "tool_action_shape",
        "auto_classify": "MEDIUM",
        "suggested_action": "Tool signature mismatch — introspect via execute_code or use batch shape `operations: [{action,...}]`.",
        "playbook_ref": "playbook/tool_action_shape/v1",
    },
    {
        "signature": r"Timed?out.*subprocess",
        "category": "subprocess_timeout",
        "auto_classify": "MEDIUM",
        "suggested_action": "Naive subprocess grep pada filesystem besar — pakai targeted path atau ripgrep dengan file_glob.",
        "playbook_ref": "playbook/grep_scope/v1",
    },
    {
        "signature": r"Permission denied \(publickey",
        "category": "ssh_auth",
        "auto_classify": "HIGH",
        "suggested_action": "Key mismatch. Cek `vps_project.json`, jalankan matrix scan {key}x{user}x{host}.",
        "playbook_ref": "playbook/ssh_key_matrix/v1",
    },
    {
        "signature": r"NXDOMAIN",
        "category": "dns_missing",
        "auto_classify": "LOW",
        "suggested_action": "Domain belum di-pointing. Cek registrar + DNS zone.",
        "playbook_ref": None,
    },
    {
        "signature": r"port \d+.*not listening|No listening",
        "category": "service_down",
        "auto_classify": "HIGH",
        "suggested_action": "Probe via curl+ss, cek PM2/systemd, restart kalau supervisor turun.",
        "playbook_ref": None,
    },
    {
        "signature": r"Loop.*same_tool.*count=\d+",
        "category": "agent_loop",
        "auto_classify": "HIGH",
        "suggested_action": "Tool stuck — introspect, fallback ke variant, atau escalate ke Bos.",
        "playbook_ref": None,
    },
]

SEED_PLAYBOOKS: Dict[str, Dict[str, Any]] = {
    "playbook/tool_action_shape/v1": {
        "title": "Tool action shape mismatch",
        "steps": [
            "1. Introspect tool via execute_code (import hermes_tools, dir(), get args).",
            "2. Periksa signature — `old_text` vs `content` vs `operations` batch.",
            "3. Coba fallback shape: jika `remove`/`replace` gagal, pakai `add` untuk tambah entry baru yang justru replace.",
            "4. Jangan loop >3 — escalate.",
        ],
        "proven_count": 0,
    },
    "playbook/grep_scope/v1": {
        "title": "Naive grep timeout pada filesystem besar",
        "steps": [
            "1. Pakai search_files (ripgrep) bukan subprocess grep.",
            "2. Set path spesifik — hindari /root seluruhnya.",
            "3. Tambahkan timeout pendek (10-15s) + file_glob.",
            "4. Kalau tetap timeout → pecah per-zona (skills/, scripts/, memory/).",
        ],
        "proven_count": 0,
    },
    "playbook/ssh_key_matrix/v1": {
        "title": "SSH ke VPS — key/user/host scanning",
        "steps": [
            "1. Lihat vps_project.json untuk daftar kredensial.",
            "2. Jalankan matrix: for key in keys; for user in users; for host in hosts.",
            "3. Cek sha256 fingerprint key — duplicate keys sering bikin bingung.",
            "4. Confirm successful match → re-use working combo.",
        ],
        "proven_count": 0,
    },
}


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


def today_id_prefix() -> str:
    """Bug-ID uses local date (server TZ) — lebih manusiawi dibanding UTC."""
    return datetime.now().strftime("%Y%m%d")


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def severity_rank(s: str) -> int:
    return {"low": 0, "medium": 1, "high": 2, "critical": 3}.get(s.lower(), 1)


@dataclass
class Bug:
    bug_id: str
    detected_at: str
    trigger: str
    status: str
    symptom: str
    root_cause: str = ""
    files_touched: List[str] = field(default_factory=list)
    fix_diff: str = ""
    regression_test: str = ""
    category: str = "uncategorized"
    severity: str = "medium"
    resolution_s: Optional[int] = None
    attempt_count: int = 0
    lesson: str = ""
    reusable_pattern: str = ""
    heuristic_signature: str = ""
    confidence: str = "low"
    verified_by: str = ""
    resolved_at: Optional[str] = None
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Bug":
        # Be tolerant terhadap field hilang.
        invalid = {"ts", "stdout", "stderr"} & set(d.keys())
        for k in invalid:
            d.pop(k, None)
        kw = {k: v for k, v in d.items() if k in cls.__dataclass_fields__}  # type: ignore[attr-defined]
        return cls(**kw)


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------


class BugLedger:
    """Penjaga bug_ledger.jsonl + heuristic db."""

    def __init__(self, ledger_path: Path = BUG_LEDGER, heuristic_path: Path = HEURISTIC_DB):
        self.ledger_path = ledger_path
        self.heuristic_path = heuristic_path

    # --- ledger ---
    def load(self) -> List[Bug]:
        if not self.ledger_path.exists():
            return []
        out: List[Bug] = []
        with self.ledger_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    d = json.loads(line)
                    out.append(Bug.from_dict(d))
                except json.JSONDecodeError:
                    continue
        return out

    def append(self, bug: Bug) -> None:
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        with self.ledger_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(bug.to_dict(), ensure_ascii=False) + "\n")

    def update(self, bug: Bug) -> None:
        """Replace bug_id entry in-place. If multiple, keep other entries intact."""
        bugs = self.load()
        replaced = False
        with self.ledger_path.open("w", encoding="utf-8") as f:
            for b in bugs:
                if b.bug_id == bug.bug_id:
                    f.write(json.dumps(bug.to_dict(), ensure_ascii=False) + "\n")
                    replaced = True
                else:
                    f.write(json.dumps(b.to_dict(), ensure_ascii=False) + "\n")
            if not replaced:
                f.write(json.dumps(bug.to_dict(), ensure_ascii=False) + "\n")

    # --- heuristics ---
    def load_heuristics(self) -> Dict[str, Any]:
        if not self.heuristic_path.exists():
            db = self._seed_heuristic_db()
            self.save_heuristics(db)
            return db
        try:
            return json.loads(self.heuristic_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return self._seed_heuristic_db()

    def save_heuristics(self, db: Dict[str, Any]) -> None:
        self.heuristic_path.parent.mkdir(parents=True, exist_ok=True)
        self.heuristic_path.write_text(json.dumps(db, ensure_ascii=False, indent=2), encoding="utf-8")

    def _seed_heuristic_db(self) -> Dict[str, Any]:
        return {
            "version": 1,
            "last_evolved": now_utc_iso(),
            "heuristics": list(SEED_HEURISTICS),
            "playbooks": {k: dict(v) for k, v in SEED_PLAYBOOKS.items()},
        }


# ---------------------------------------------------------------------------
# Bug ID allocation
# ---------------------------------------------------------------------------


def next_bug_id(existing: Iterable[Bug]) -> str:
    today = today_id_prefix()
    max_n = 0
    for b in existing:
        m = re.match(rf"BUGID-{today}-(\d+)", b.bug_id)
        if m:
            max_n = max(max_n, int(m.group(1)))
    return f"BUGID-{today}-{max_n + 1:04d}"


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------


@dataclass
class Detection:
    signature: str
    category: str
    severity: str
    matched_text: str
    suggested_action: str
    playbook_ref: Optional[str]


def detect(error_text: str, heuristic_db: Dict[str, Any]) -> Optional[Detection]:
    """Match error text against heuristics."""
    if not error_text:
        return None
    for h in heuristic_db.get("heuristics", []):
        sig = h.get("signature", "")
        try:
            if re.search(sig, error_text):
                return Detection(
                    signature=sig,
                    category=h.get("category", "uncategorized"),
                    severity=h.get("auto_classify", "MEDIUM").lower(),
                    matched_text=error_text[:400],
                    suggested_action=h.get("suggested_action", ""),
                    playbook_ref=h.get("playbook_ref"),
                )
        except re.error:
            continue
    return None


# ---------------------------------------------------------------------------
# Core — BugHunter
# ---------------------------------------------------------------------------


class BugHunter:
    def __init__(self, ledger_path: Path = BUG_LEDGER, heuristic_path: Path = HEURISTIC_DB):
        self.ledger = BugLedger(ledger_path, heuristic_path)
        self.heuristic_db = self.ledger.load_heuristics()
        self.bugs: List[Bug] = self.ledger.load()

    # ---- DETECT -------------------------------------------------------
    def scan_input(self, text: str) -> Optional[Detection]:
        return detect(text, self.heuristic_db)

    def scan(self, scope: str = ".", severity: str = "low") -> List[Detection]:
        """
        Proactive scan: sweep `scope` for known heuristic patterns.
        Severity filter applied after detection.
        Reads `*.py`, `*.md`, `*.yaml`, `*.json`, `*.sh`, `*.log` in PROFILE_ROOT/scope.

        NOTE: implemented as best-effort 'pattern sweep' — bukan formal static analysis.
        """
        findings: List[Detection] = []
        chosen = PROFILE_ROOT / scope if scope != "." else PROFILE_ROOT
        if not chosen.exists():
            return findings
        exts = {".py", ".md", ".yaml", ".yml", ".json", ".sh", ".log"}
        cutoff = severity_rank(severity)
        try:
            for root, _, files in os.walk(chosen):
                if "node_modules" in root or ".git" in root or "sessions" in root:
                    continue
                for name in files:
                    p = Path(root) / name
                    if p.suffix not in exts:
                        continue
                    try:
                        text = p.read_text(encoding="utf-8", errors="ignore")
                    except Exception:
                        continue
                    if name in {"bug_ledger.jsonl", "bug_hunter_heuristics.json"}:
                        continue
                    # Avoid scanning seeded heuristics literal in OUR skill file.
                    for d in self._scan_text(text):
                        if severity_rank(d.severity) >= cutoff:
                            findings.append(d)
                if len(findings) > 200:  # safety cap
                    break
        except Exception:
            pass
        return findings

    def _scan_text(self, text: str) -> List[Detection]:
        out = []
        for h in self.heuristic_db.get("heuristics", []):
            sig = h.get("signature", "")
            try:
                if re.search(sig, text):
                    out.append(
                        Detection(
                            signature=sig,
                            category=h.get("category", "uncategorized"),
                            severity=h.get("auto_classify", "MEDIUM").lower(),
                            matched_text=text[:200],
                            suggested_action=h.get("suggested_action", ""),
                            playbook_ref=h.get("playbook_ref"),
                        )
                    )
                    break  # one hit per heuristic per file
            except re.error:
                continue
        return out

    # ---- DIAGNOSE -----------------------------------------------------
    def diagnose(self, error: str = "", file: Optional[str] = None, context: str = "") -> Dict[str, Any]:
        d = self.scan_input(error)
        result: Dict[str, Any] = {
            "input": {"error": error[:500], "file": file, "context": context[:200]},
            "matched_heuristic": None,
            "hypotheses": [],
            "suggested_actions": [],
            "confidence": "low",
        }
        if d:
            result["matched_heuristic"] = d.signature
            result["confidence"] = "high"
            result["suggested_actions"].append(d.suggested_action)
            if (
                d.playbook_ref
                and d.playbook_ref in (self.heuristic_db.get("playbooks") or {})
            ):
                pb = self.heuristic_db["playbooks"][d.playbook_ref]
                result["suggested_actions"].append(f"PLAYBOOK {d.playbook_ref}: " + " | ".join(pb.get("steps", [])))
        if file and os.path.exists(file):
            try:
                with open(file, "r", encoding="utf-8", errors="ignore") as f:
                    snippet = f.read(2000)
                result["file_snippet_excerpt"] = snippet[:500]
            except Exception:
                pass
        # Generic hypotheses kalau tidak ada match
        if not d:
            result["hypotheses"] = [
                "Apakah ini race condition? Cek log timing.",
                "Apakah config/value boundary (negative/null/empty)?",
                "Apakah dependency version drift? Cek lockfile.",
                "Apakah permission/owner salah?",
            ]
        return result

    # ---- FIX ----------------------------------------------------------
    def fix(self, bug_id: str, auto_apply: bool = False) -> Dict[str, Any]:
        bug = next((b for b in self.bugs if b.bug_id == bug_id), None)
        if not bug:
            return {"ok": False, "error": f"bug_id {bug_id} tidak ditemukan"}

        plan = {
            "ok": True,
            "bug_id": bug_id,
            "category": bug.category,
            "severity": bug.severity,
            "patch_actions": [],
            "regression_test_path": bug.regression_test,
            "warnings": [],
            "auto_apply": auto_apply,
        }

        # Tool action shape (memory tool) — concrete fix
        if bug.category == "tool_action_shape":
            plan["patch_actions"] = [
                {
                    "step": 1,
                    "action": "introspect_signature",
                    "tool": "execute_code",
                    "command": "from hermes_tools import dir; print([n for n in dir()])",
                },
                {
                    "step": 2,
                    "action": "send_batch_shape",
                    "tool": "memory",
                    "shape": {"operations": [{"action": "add", "content": "..."}]},
                },
                {
                    "step": 3,
                    "action": "fallback_add_new_entry",
                    "tool": "memory",
                    "shape": {"action": "add", "content": "...", "target": "memory"},
                    "rationale": "Jika tu replace/remove gagal, add entry baru yang lebih baik. Jangan loop.",
                },
            ]
            plan["warnings"].append("Tool runtime bug — bukan masalah source code; mitigation in skill layer.")
            bug.attempt_count += 1
            bug.status = "verified"
            bug.verified_by = "manual"
            bug.resolution_s = 5
            bug.resolved_at = now_utc_iso()
        # Other categories: placeholder; kita belum punya auto-patch generic
        else:
            plan["patch_actions"] = [
                {
                    "step": 1,
                    "action": "follow_suggested_action",
                    "from_heuristic": True,
                    "debug_guidance": "Terapkan suggested_action heuristic db.",
                },
            ]
            plan["warnings"].append("Generic category — manual application required.")
            bug.attempt_count += 1
            bug.status = "in_progress"

        # Record (always) even if not auto applied
        self.ledger.update(bug)
        return plan

    # ---- VERIFY -------------------------------------------------------
    def verify(self, bug_id: str, run_judge: bool = False) -> Dict[str, Any]:
        bug = next((b for b in self.bugs if b.bug_id == bug_id), None)
        if not bug:
            return {"ok": False, "error": f"bug_id {bug_id} tidak ditemukan"}
        # Heuristic verify: ada regression_test path?
        ok = bool(bug.regression_test)
        out = {
            "bug_id": bug_id,
            "status": "verified" if ok else "needs_regression_test",
            "regression_test": bug.regression_test,
            "lesson_persisted": bool(bug.lesson),
            "heuristic_promoted": bool(bug.heuristic_signature),
            "evidence_emitted": False,
        }
        # v1.1 — judge verification hook
        if run_judge and bug.files_touched:
            judge_results = []
            for fp in bug.files_touched:
                jr = run_judge_verify(file=fp, task=f"bug-hunter verify {bug_id}")
                judge_results.append({"file": fp, **jr})
            out["judge_results"] = judge_results
        # v1.3 — emit evidence ke ledger
        verdict = "verified" if ok else "needs_regression_test"
        evid = emit_evidence(
            bug_id=bug_id,
            capability=bug.category.upper()[:20],
            status="ok" if ok else "warn",
            description=f"bug-hunter verify: {verdict}",
            extra={
                "severity": bug.severity,
                "fix_attempt": bug.attempt_count,
                "regression_test_path": bug.regression_test,
                "judge_run": run_judge,
            },
        )
        if evid:
            out["evidence_id"] = evid
            out["evidence_emitted"] = True
        return out

    # ---- LEARN --------------------------------------------------------
    def learn(
        self,
        symptom: str,
        root_cause: str,
        category: str = "uncategorized",
        severity: str = "medium",
        heuristic_signature: str = "",
        lesson: str = "",
        reusable_pattern: str = "",
        files_touched: Optional[List[str]] = None,
        regression_test: str = "",
        fix_diff: str = "",
        trigger: str = "manual",
        confidence: str = "medium",
        tags: Optional[List[str]] = None,
        verified_by: str = "manual",
    ) -> Bug:
        bug_id = next_bug_id(self.bugs)
        bug = Bug(
            bug_id=bug_id,
            detected_at=now_utc_iso(),
            trigger=trigger,
            status="open",
            symptom=symptom,
            root_cause=root_cause,
            files_touched=files_touched or [],
            fix_diff=fix_diff,
            regression_test=regression_test,
            category=category,
            severity=severity,
            attempt_count=0,
            lesson=lesson,
            reusable_pattern=reusable_pattern,
            heuristic_signature=heuristic_signature,
            confidence=confidence,
            verified_by=verified_by,
            tags=tags or [],
        )
        self.ledger.append(bug)
        self.bugs.append(bug)
        # Auto-promote heuristic kalau belum ada
        if heuristic_signature:
            self._promote_heuristic(heuristic_signature, category, severity, lesson, reusable_pattern)
        return bug

    def _promote_heuristic(
        self,
        signature: str,
        category: str,
        severity: str,
        lesson: str,
        reusable_pattern: str,
    ) -> None:
        db = self.heuristic_db
        for h in db.get("heuristics", []):
            if h.get("signature") == signature:
                h["occurrences"] = h.get("occurrences", 0) + 1
                break
        else:
            db.setdefault("heuristics", []).append(
                {
                    "signature": signature,
                    "category": category,
                    "auto_classify": severity.upper(),
                    "suggested_action": lesson or reusable_pattern or "manual review",
                    "playbook_ref": None,
                    "occurrences": 1,
                    "first_seen": now_utc_iso(),
                }
            )
        self.ledger.save_heuristics(db)

    # ---- EVOLVE -------------------------------------------------------
    def evolve(self, force: bool = False) -> Dict[str, Any]:
        db = self.heuristic_db
        # Promote category → playbook kalau proven_count >= threshold
        threshold = 3
        by_cat: Dict[str, int] = Counter()
        for b in self.bugs:
            by_cat[b.category] += 1
        promoted: List[str] = []
        for cat, count in by_cat.items():
            if count >= threshold:
                pb_id = f"playbook/{cat}/v1"
                if pb_id not in db.setdefault("playbooks", {}):
                    db["playbooks"][pb_id] = {
                        "title": f"Auto-derived playbook for {cat}",
                        "steps": [
                            f"1. Verify symptom matches category {cat}.",
                            f"2. Run heuristic detect() with text containing '{cat}' signature.",
                            "3. Apply documented patch from book.",
                            "4. Verify regression test passes.",
                        ],
                        "proven_count": count,
                    }
                    promoted.append(pb_id)
                else:
                    db["playbooks"][pb_id]["proven_count"] = count

        # Back-link heuristics → playbook
        new_heuristics = 0
        for h in db.get("heuristics", []):
            cat = h.get("category", "")
            if cat and not h.get("playbook_ref"):
                candidate = f"playbook/{cat}/v1"
                if candidate in db.get("playbooks",):
                    h["playbook_ref"] = candidate
                    new_heuristics += 1

        db["version"] = max(db.get("version", 1), 1)
        db["last_evolved"] = now_utc_iso()
        self.ledger.save_heuristics(db)

        # Garbage collect: keep last 365 entries (tidak benar-benar hapus kalau verified; cukup truncate append-only log size)
        too_old = 0
        if len(self.bugs) > 365:
            # Tidak menghapus file append-only — hanya info kalau sudah panjang
            too_old = len(self.bugs) - 365

        return {
            "ok": True,
            "promoted_playbooks": promoted,
            "heuristics_backlinked": new_heuristics,
            "ledger_size": len(self.bugs),
            "ledger_truncate_marker": too_old,
            "forced": force,
        }

    # ---- INTROSPECT ---------------------------------------------------
    def stats(self) -> Dict[str, Any]:
        if not self.bugs:
            return {"ok": True, "count": 0}
        by_status = Counter(b.status for b in self.bugs)
        by_severity = Counter(b.severity for b in self.bugs)
        by_category = Counter(b.category for b in self.bugs)
        resolved = [b.resolution_s for b in self.bugs if b.resolution_s]
        mttr = sum(resolved) / len(resolved) if resolved else 0
        return {
            "ok": True,
            "count": len(self.bugs),
            "by_status": dict(by_status),
            "by_severity": dict(by_severity),
            "by_category": dict(by_category),
            "mttr_s": round(mttr, 1),
            "heuristic_count": len(self.heuristic_db.get("heuristics", [])),
            "playbook_count": len(self.heuristic_db.get("playbooks", [])),
        }

    def playbook(self, top: int = 10) -> str:
        from collections import Counter
        cat_count: Counter = Counter()
        for b in self.bugs:
            if b.category:
                cat_count[b.category] += 1
        lines = ["# bug-hunter — Top Playbook Patterns", ""]
        for cat, n in cat_count.most_common(top):
            pb_id = f"playbook/{cat}/v1"
            steps = self.heuristic_db.get("playbooks", {}).get(pb_id, {}).get("steps", [])
            lines.append(f"## {cat} — occurrences={n}")
            if steps:
                lines.append("")
                lines.extend(steps)
            lines.append("")
        if not cat_count:
            lines.append("_(no bugs recorded yet — grow the ledger!)_")
        return "\n".join(lines)

    # ---- list ---------------------------------------------------------
    def list_bugs(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        out = []
        for b in self.bugs:
            if status and b.status != status:
                continue
            out.append(b.to_dict())
        return out


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _make_bug_from_args(args: argparse.Namespace) -> Bug:
    return Bug(
        bug_id=getattr(args, "bug_id", None) or next_bug_id([]),
        detected_at=now_utc_iso(),
        trigger=getattr(args, "trigger", "manual"),
        status=getattr(args, "status", "open"),
        symptom=getattr(args, "symptom", ""),
        root_cause=getattr(args, "root_cause", ""),
        regression_test=getattr(args, "regression", ""),
        category=getattr(args, "category", "uncategorized"),
        severity=getattr(args, "severity", "medium"),
        lesson=getattr(args, "lesson", ""),
        reusable_pattern=getattr(args, "reusable_pattern", ""),
        heuristic_signature=getattr(args, "heap_signature", ""),
        confidence=getattr(args, "confidence", "medium"),
        verified_by=getattr(args, "verified_by", ""),
    )


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="bug-hunter", description="bug-hunter: detect/diagnose/fix/learn/evolve")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("scan", help="sweep scope untuk known heuristic patterns")
    s.add_argument("--scope", default=".")
    s.add_argument("--severity", default="low", choices=["low", "medium", "high", "critical"])

    d = sub.add_parser("diagnose", help="diagnose error message")
    d.add_argument("--error", default="")
    d.add_argument("--file", default=None)
    d.add_argument("--context", default="")

    f = sub.add_parser("fix", help="apply/plan fix for known bug_id")
    f.add_argument("--bug-id", required=True)
    f.add_argument("--yes", action="store_true")

    l = sub.add_parser("learn", help="append bug entry ke ledger + promote heuristic")
    l.add_argument("--symptom", required=True)
    l.add_argument("--root-cause", dest="root_cause", default="")
    l.add_argument("--category", default="uncategorized")
    l.add_argument("--severity", default="medium", choices=["low", "medium", "high", "critical"])
    l.add_argument("--heap-signature", dest="heap_signature", default="", help="regex pattern untuk heuristic auto-match")
    l.add_argument("--lesson", default="")
    l.add_argument("--reusable-pattern", dest="reusable_pattern", default="")
    l.add_argument("--regression", default="")
    l.add_argument("--fix-diff", dest="fix_diff", default="")
    l.add_argument("--trigger", default="manual")
    l.add_argument("--confidence", default="medium")
    l.add_argument("--tags", nargs="*", default=[])
    l.add_argument("--verified-by", dest="verified_by", default="manual")

    e = sub.add_parser("evolve", help="run heuristic + playbook evolution cycle")
    e.add_argument("--force", action="store_true")

    lst = sub.add_parser("list", help="list bug ledger (filter by status)")
    lst.add_argument("--status", default=None)

    sub.add_parser("stats", help="aggregated stats")

    pb = sub.add_parser("playbook", help="export top fix patterns ke Markdown")
    pb.add_argument("--top", type=int, default=10)

    v = sub.add_parser("verify", help="verify bug_id fix (regression test presence)")
    v.add_argument("--bug-id", required=True)
    v.add_argument("--judge", action="store_true", help="hook ilma_judge_system setelah fix")

    sub.add_parser("init", help="initialize/reset ledger + heuristic db")

    t = sub.add_parser("trigger-scan", help="scan chat text untuk bug-trigger patterns (v1.2)")
    t.add_argument("--text", required=True, help="text dari user/assistant turn")
    t.add_argument("--auto-learn", action="store_true", help="auto append ke ledger")

    crn = sub.add_parser("cron-template", help="emit Cron jobs untuk nightly scan + weekly evolve (v1.4)")
    crn.add_argument("--emit", action="store_true", help="tulis ke ~/.hermes/profiles/ilma/cron/jobs.json (idempotent)")

    return p


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    hunter = BugHunter()

    if args.cmd == "scan":
        findings = hunter.scan(args.scope, args.severity)
        print(json.dumps({"ok": True, "count": len(findings), "findings": [vars(d) for d in findings[:20]]}, indent=2))
        return 0
    if args.cmd == "diagnose":
        out = hunter.diagnose(args.error, args.file, args.context)
        print(json.dumps(out, indent=2))
        return 0
    if args.cmd == "fix":
        out = hunter.fix(args.bug_id, auto_apply=args.yes)
        print(json.dumps(out, indent=2))
        return 0 if out.get("ok") else 1
    if args.cmd == "learn":
        bug = hunter.learn(
            symptom=args.symptom,
            root_cause=args.root_cause,
            category=args.category,
            severity=args.severity,
            heuristic_signature=args.heap_signature,
            lesson=args.lesson,
            reusable_pattern=args.reusable_pattern,
            regression_test=args.regression,
            fix_diff=args.fix_diff,
            trigger=args.trigger,
            confidence=args.confidence,
            tags=args.tags or [],
            verified_by=args.verified_by,
        )
        print(json.dumps({"ok": True, "bug_id": bug.bug_id}, indent=2))
        return 0
    if args.cmd == "evolve":
        out = hunter.evolve(force=args.force)
        print(json.dumps(out, indent=2))
        return 0
    if args.cmd == "list":
        out = hunter.list_bugs(args.status)
        for b in out:
            print(f"[{b['bug_id']}] {b['status']} {b['severity']}/{b['category']}: {b['symptom'][:80]}")
        return 0
    if args.cmd == "stats":
        out = hunter.stats()
        print(json.dumps(out, indent=2))
        return 0
    if args.cmd == "playbook":
        print(hunter.playbook(args.top))
        return 0
    if args.cmd == "verify":
        out = hunter.verify(args.bug_id, run_judge=args.judge)
        print(json.dumps(out, indent=2))
        return 0 if out.get("status") == "verified" else 1
    if args.cmd == "init":
        BUG_LEDGER.parent.mkdir(parents=True, exist_ok=True)
        BUG_LEDGER.write_text("", encoding="utf-8")
        hunter = BugHunter()  # rebuild cached
        print(json.dumps({"ok": True, "ledger": str(BUG_LEDGER), "heuristics": str(HEURISTIC_DB)}, indent=2))
        return 0
    if args.cmd == "trigger-scan":
        hits = detect_chat_triggers(args.text)
        out = {"ok": True, "trigger_count": len(hits), "triggers": hits}
        if args.auto_learn and hits:
            for h in hits:
                bug = hunter.learn(
                    symptom=h["summary"],
                    root_cause="auto-detected dari chat trigger pattern",
                    category=h["signature"],
                    severity=h["severity"].lower(),
                    heuristic_signature=h["signature"],
                    lesson="Auto-learned dari chat pattern trigger",
                    trigger="auto_trigger",
                )
                out.setdefault("learned", []).append(bug.bug_id)
        print(json.dumps(out, indent=2))
        return 0
    if args.cmd == "cron-template":
        bh_path = Path(__file__).resolve()
        jobs = {
            "note": "bug-hunter auto-generated cron template (v1.4)",
            "generated_at": now_utc_iso(),
            "jobs": [
                {
                    "id": "bug_hunter_nightly_scan",
                    "name": "bug-hunter nightly scan (medium+)",
                    "schedule": "0 3 * * *",
                    "command": f"python3 {bh_path} scan --scope scripts/ --severity medium",
                    "deliver": "local",
                    "enabled": True,
                },
                {
                    "id": "bug_hunter_weekly_evolve",
                    "name": "bug-hunter weekly evolve (heuristic + playbook)",
                    "schedule": "0 4 * * 0",
                    "command": f"python3 {bh_path} evolve",
                    "deliver": "local",
                    "enabled": True,
                },
            ],
        }
        target = PROFILE_ROOT / "cron" / "bug_hunter_jobs.json"
        if args.emit:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(jobs, indent=2, ensure_ascii=False), encoding="utf-8")
            print(json.dumps({"ok": True, "written_to": str(target)}, indent=2))
        else:
            print(json.dumps(jobs, indent=2))
        return 0

    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
