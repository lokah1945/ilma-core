#!/usr/bin/env python3
"""
ILMA Telemetry Analyzer v1.0  (2026-06-01)
==========================================
Mines real runtime telemetry (errors.log, agent.log) for RECURRING failure
patterns and converts them into actionable learnings + a structured findings
report the autonomous loop can act on.

This is the "eyes" of substantive self-improvement: the agent learns from what
actually goes wrong in production, not from ceremony.

Usage:
    python3 ilma_telemetry_analyzer.py            # analyze + log learnings
    python3 ilma_telemetry_analyzer.py --json     # print findings JSON only
"""
from __future__ import annotations
import re, json, sys, os
from pathlib import Path
from collections import Counter, defaultdict
from datetime import datetime

ILMA_ROOT = Path("/root/.hermes/profiles/ilma")
LOGS = ILMA_ROOT / "logs"
OUT = ILMA_ROOT / ".learnings" / "telemetry_findings.json"
MAX_BYTES = 4_000_000  # tail cap per log

# (pattern_name, regex, severity, suggested_action)
PATTERNS = [
    ("tool_loop",          re.compile(r"Tool loop (warning|hard.?stop)|same_tool_failure", re.I), "high",
     "Inspect the looping tool + add guard / alternate path"),
    ("git_auth_fail",      re.compile(r"could not read Username for 'https://github\.com'|Authentication failed for 'https://github", re.I), "medium",
     "Refresh GitHub token / ensure credential helper + GIT_TERMINAL_PROMPT=0"),
    ("model_empty",        re.compile(r"EMPTY_RESPONSE|empty content|empty response", re.I), "high",
     "Mark model unavailable / route to healthy model"),
    ("model_auth",         re.compile(r"Authentication failed|User not found|API key is required|Not found for account", re.I), "high",
     "Fix/rotate provider key or exclude dead model from free pool"),
    ("model_timeout",      re.compile(r"timed out|timeout|TimeoutError|Read timed out", re.I), "medium",
     "Apply latency penalty / lower per-call timeout / prefer faster model"),
    ("import_error",       re.compile(r"ImportError|ModuleNotFoundError|cannot import name", re.I), "high",
     "Repair broken import / wiring"),
    ("rate_limit",         re.compile(r"rate.?limit|429|Resource temporarily unavailable|Too Many Requests", re.I), "medium",
     "Back off / raise TasksMax / spread load across providers"),
    ("traceback",          re.compile(r"Traceback \(most recent call last\)", re.I), "high",
     "Investigate exception root cause"),
]


def _tail(path: Path, max_bytes: int = MAX_BYTES) -> str:
    try:
        sz = path.stat().st_size
        with open(path, "rb") as f:
            if sz > max_bytes:
                f.seek(sz - max_bytes)
            return f.read().decode("utf-8", errors="replace")
    except Exception:
        return ""


def analyze() -> dict:
    counts: Counter = Counter()
    samples: dict = defaultdict(list)
    actions: dict = {}
    sev: dict = {}

    log_files = []
    if LOGS.exists():
        for name in ["errors.log", "errors.log.1", "agent.log", "gateway.log"]:
            p = LOGS / name
            if p.exists():
                log_files.append(p)

    for lf in log_files:
        text = _tail(lf)
        for line in text.splitlines():
            for name, rx, severity, action in PATTERNS:
                if rx.search(line):
                    counts[name] += 1
                    sev[name] = severity
                    actions[name] = action
                    if len(samples[name]) < 3:
                        samples[name].append(line.strip()[:240])

    findings = []
    for name, cnt in counts.most_common():
        findings.append({
            "pattern": name,
            "count": cnt,
            "severity": sev.get(name, "medium"),
            "suggested_action": actions.get(name, ""),
            "samples": samples.get(name, []),
            # recurring = worth a learning
            "recurring": cnt >= 3,
        })

    report = {
        "generated_at": datetime.now().isoformat(),
        "logs_scanned": [str(p.name) for p in log_files],
        "total_matches": sum(counts.values()),
        "findings": findings,
    }
    return report


def log_learnings(report: dict) -> int:
    """Turn recurring findings into actionable learnings (deduped by signature)."""
    logged = 0
    try:
        sys.path.insert(0, str(ILMA_ROOT))
        from ilma_self_improvement import get_learning_logger
        ll = get_learning_logger()
        # build a set of existing pending signatures to avoid dupes
        existing = set()
        try:
            for e in ll.get_pending(limit=200):
                existing.add((e.get("area"), e.get("summary")))
        except Exception:
            pass
        for f in report["findings"]:
            if not f["recurring"]:
                continue
            summary = f"[telemetry] recurring {f['pattern']} x{f['count']}"
            area = f"telemetry/{f['pattern']}"
            if (area, summary) in existing:
                continue
            try:
                ll.log_knowledge_gap(
                    summary=summary,
                    what_was_expected="clean run",
                    what_actually_happened=" | ".join(f["samples"][:2]) or f["pattern"],
                    area=area,
                    priority=("high" if f["severity"] == "high" else "medium"),
                    suggested_fix=f["suggested_action"],
                )
                logged += 1
            except TypeError:
                # older signature fallback
                try:
                    ll.log_knowledge_gap(summary, "clean run", f["pattern"])
                    logged += 1
                except Exception:
                    pass
            except Exception:
                pass
    except Exception as e:
        print(f"[telemetry] learning log skipped: {e}")
    return logged


def main():
    report = analyze()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2))
    if "--json" in sys.argv:
        print(json.dumps(report, indent=2))
        return
    logged = log_learnings(report)
    print(f"=== ILMA Telemetry Analyzer ===")
    print(f"logs scanned: {report['logs_scanned']}")
    print(f"total matches: {report['total_matches']}")
    print(f"recurring patterns: {sum(1 for f in report['findings'] if f['recurring'])}")
    for f in report["findings"][:10]:
        flag = "‼️" if f["recurring"] else "·"
        print(f"  {flag} {f['pattern']:16} x{f['count']:<4} [{f['severity']}] {f['suggested_action'][:50]}")
    print(f"learnings logged: {logged}  -> {OUT.name}")


if __name__ == "__main__":
    main()
