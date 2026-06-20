#!/usr/bin/env python3
"""
ILMA Self-Improvement System
============================
Provides TWO complementary self-improvement systems:

1. SelfImprovementEngine (from ilma_core) — event-based learning loop
   - record_event(), run_optimization_cycle(), get_quality_trend(), get_insights()
   - Tracks learning events with quality metrics

2. LearningLogger — file-based persistent learnings
   - log_error(), log_correction(), log_insight(), log_knowledge_gap(), log_best_practice()
   - Writes to .learnings/ (LEARNINGS.md, ERRORS.md, FEATURE_REQUESTS.md, DNA_UPDATES.md)
   - Provides get_pending(), get_stats(), resolve(), promote_to_dna()

Version: 2.0 — Unified: both systems available from single import
"""

# ─── SelfImprovementEngine (from ilma_core) ───────────────────────────────────
# Re-export so ilma.py can import from here instead of ilma_core subpath
import sys as _sys
from pathlib import Path as _Path

# Add ilma_core to path if available
_ilma_core_path = _Path(__file__).parent / "ilma_core"
if _ilma_core_path.exists():
    _sys.path.insert(0, str(_Path(__file__).parent))
    try:
        from ilma_core.ilma_self_improvement import (
            SelfImprovementEngine,
            LearningEvent,
            OptimizationSuggestion,
        )
        __all__ = [
            "SelfImprovementEngine",
            "LearningEvent",
            "OptimizationSuggestion",
            "LearningLogger",
            "get_learning_logger",
            "log_error",
            "log_learning",
            "log_correction",
            "log_insight",
            "log_knowledge_gap",
            "log_best_practice",
            "log_feature_request",
            "get_pending",
            "get_learning_stats",
        ]
    except ImportError:
        SelfImprovementEngine = None
        __all__ = [
            "LearningLogger",
            "get_learning_logger",
            "log_error",
            "log_learning",
            "log_correction",
            "log_insight",
            "log_knowledge_gap",
            "log_best_practice",
            "log_feature_request",
            "get_pending",
            "get_learning_stats",
        ]
else:
    SelfImprovementEngine = None
    __all__ = [
        "LearningLogger",
        "get_learning_logger",
        "log_error",
        "log_learning",
        "log_correction",
        "log_insight",
        "log_knowledge_gap",
        "log_best_practice",
        "log_feature_request",
        "get_pending",
        "get_learning_stats",
    ]

# ─── LearningLogger (new v2 system) ──────────────────────────────────────────

import hashlib as _hashlib
import json as _json
import logging as _logging
import os as _os
import re as _re
import threading as _threading
from datetime import datetime as _datetime
from enum import Enum as _Enum
from pathlib import Path as _Path
from typing import Any as _Any, Dict as _Dict, List as _List, Optional as _Optional

_logger = _logging.getLogger(__name__)

ILMA_ROOT = _Path("/root/.hermes/profiles/ilma")
LEARNINGS_DIR = ILMA_ROOT / ".learnings"


class LearningCategory(_Enum):
    CORRECTION = "correction"
    INSIGHT = "insight"
    KNOWLEDGE_GAP = "knowledge_gap"
    BEST_PRACTICE = "best_practice"
    ERROR = "error"
    FEATURE_REQUEST = "feature_request"


class Priority(_Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class LearningLogger:
    """
    Central file-based self-improvement logger.
    
    Captures:
    - Errors: command failures, integration errors, exceptions
    - Corrections: user corrections, wrong assumptions
    - Insights: better approaches, discoveries
    - Knowledge gaps: missing knowledge, outdated info
    - Best practices: proven patterns
    - Feature requests: capabilities user wanted but missing
    
    Auto-promotes high-value learnings to DNA_UPDATES.md.
    """
    
    def __init__(self, learnings_dir: _Optional[_Path] = None):
        self.learnings_dir = learnings_dir or LEARNINGS_DIR
        self._lock = _threading.Lock()
        self._counter_cache: _Dict[str, int] = {}
        self._ensure_init()
    
    def _ensure_init(self):
        self.learnings_dir.mkdir(parents=True, exist_ok=True)
        files = {
            "LEARNINGS.md": "# Learnings\n\nCorrections, insights, and knowledge gaps.\n\n**Categories**: correction | insight | knowledge_gap | best_practice\n\n---\n",
            "ERRORS.md": "# Errors\n\nCommand failures and integration errors.\n\n---\n",
            "FEATURE_REQUESTS.md": "# Feature Requests\n\nCapabilities requested by the user.\n\n---\n",
            "DNA_UPDATES.md": "# ILMA DNA Updates\n\nPermanent evolution rules and behavioral guidelines.\n\n---\n",
        }
        for fname, default_content in files.items():
            path = self.learnings_dir / fname
            if not path.exists():
                path.write_text(default_content)
    
    def _get_next_id(self, prefix: str) -> str:
        today = _datetime.now().strftime("%Y%m%d")
        key = f"{prefix}:{today}"
        with self._lock:
            if key not in self._counter_cache:
                max_num = 0
                pattern = _re.compile(rf"## \[{prefix}-\d{{8}}-(\d{{3}})\]")
                for fname in ["LEARNINGS.md", "ERRORS.md", "FEATURE_REQUESTS.md"]:
                    path = self.learnings_dir / fname
                    if path.exists():
                        for line in path.read_text().splitlines():
                            m = pattern.match(line.strip())
                            if m and int(m.group(1)) > max_num:
                                max_num = int(m.group(1))
                self._counter_cache[key] = max_num
            self._counter_cache[key] += 1
            return f"{prefix}-{today}-{self._counter_cache[key]:03d}"
    
    def _checksum(self, content: str) -> str:
        return _hashlib.md5(content.encode()).hexdigest()[:12]
    
    # ─── PUBLIC API ─────────────────────────────────────────────────────────────
    
    def log_error(
        self,
        summary: str,
        error_detail: str,
        context: _Optional[_Dict[str, str]] = None,
        area: str = "unknown",
        reproducible: str = "unknown",
        related_files: _Optional[_List[str]] = None,
        priority: str = "high",
    ) -> str:
        entry_id = self._get_next_id("ERR")
        now = _datetime.now().isoformat()
        ctx_str = "\n### Context\n" + "\n".join(f"- **{k}**: {v}" for k, v in (context or {}).items())
        related_str = f"\n- **Related Files**: {', '.join(related_files)}" if related_files else ""
        entry = f"""
## [{entry_id}] {summary}

**Logged**: {now}
**Priority**: {priority}
**Status**: pending
**Area**: {area}

### Summary
{summary}

### Error
```
{error_detail}
```
{ctx_str}

### Suggested Fix
<!-- TODO: fill in fix if known -->

### Metadata
- **Reproducible**: {reproducible}{related_str}
- **Checksum**: `{self._checksum(error_detail)}`

---
"""
        return self._append("ERRORS.md", entry.strip())
    
    def log_learning(
        self,
        category: str,
        summary: str,
        details: str,
        suggested_action: _Optional[str] = None,
        source: str = "conversation",
        area: str = "unknown",
        related_files: _Optional[_List[str]] = None,
        tags: _Optional[_List[str]] = None,
        priority: str = "medium",
    ) -> str:
        entry_id = self._get_next_id("LRN")
        now = _datetime.now().isoformat()
        action_str = f"\n### Suggested Action\n{suggested_action}" if suggested_action else ""
        related_str = f"\n- **Related Files**: {', '.join(related_files)}" if related_files else ""
        tags_str = ", ".join(tags) if tags else "none"
        entry = f"""
## [{entry_id}] {category}

**Logged**: {now}
**Priority**: {priority}
**Status**: pending
**Area**: {area}

### Summary
{summary}

### Details
{details}
{action_str}

### Metadata
- **Source**: {source}{related_str}
- **Tags**: {tags_str}

---
"""
        return self._append("LEARNINGS.md", entry.strip())
    
    def log_correction(
        self,
        summary: str,
        what_was_wrong: str,
        what_is_correct: str,
        suggested_action: _Optional[str] = None,
        source: str = "user_feedback",
        area: str = "unknown",
        related_files: _Optional[_List[str]] = None,
    ) -> str:
        details = f"**What was wrong:**\n{what_was_wrong}\n\n**What is correct:**\n{what_is_correct}"
        return self.log_learning(
            category="correction", summary=summary, details=details,
            suggested_action=suggested_action, source=source, area=area,
            related_files=related_files, priority="high",
        )
    
    def log_insight(
        self,
        summary: str,
        what_discovered: str,
        why_useful: str,
        suggested_action: _Optional[str] = None,
        source: str = "self_audit",
        area: str = "unknown",
        related_files: _Optional[_List[str]] = None,
        tags: _Optional[_List[str]] = None,
    ) -> str:
        details = f"**What was discovered:**\n{what_discovered}\n\n**Why it's useful:**\n{why_useful}"
        return self.log_learning(
            category="insight", summary=summary, details=details,
            suggested_action=suggested_action, source=source, area=area,
            related_files=related_files, tags=tags, priority="medium",
        )
    
    def log_knowledge_gap(
        self,
        summary: str,
        what_was_expected: str,
        what_actually_happened: str,
        suggested_action: _Optional[str] = None,
        source: str = "conversation",
        area: str = "unknown",
        related_files: _Optional[_List[str]] = None,
    ) -> str:
        details = f"**What was expected:**\n{what_was_expected}\n\n**What actually happened:**\n{what_actually_happened}"
        return self.log_learning(
            category="knowledge_gap", summary=summary, details=details,
            suggested_action=suggested_action, source=source, area=area,
            related_files=related_files, priority="medium",
        )
    
    def log_best_practice(
        self,
        summary: str,
        pattern: str,
        when_to_use: str,
        suggested_action: _Optional[str] = None,
        source: str = "self_audit",
        area: str = "unknown",
        related_files: _Optional[_List[str]] = None,
        tags: _Optional[_List[str]] = None,
    ) -> str:
        details = f"**Pattern:**\n{pattern}\n\n**When to use:**\n{when_to_use}"
        return self.log_learning(
            category="best_practice", summary=summary, details=details,
            suggested_action=suggested_action, source=source, area=area,
            related_files=related_files, tags=tags, priority="medium",
        )
    
    def log_feature_request(
        self,
        capability: str,
        request: str,
        user_context: _Optional[str] = None,
        complexity: str = "unknown",
        area: str = "unknown",
        frequency: str = "first_time",
        related_features: _Optional[str] = None,
        priority: str = "medium",
    ) -> str:
        entry_id = self._get_next_id("FEAT")
        now = _datetime.now().isoformat()
        ctx_str = f"\n### User Context\n{user_context}" if user_context else ""
        related_str = f"\n- **Related Features**: {related_features}" if related_features else ""
        entry = f"""
## [{entry_id}] {capability}

**Logged**: {now}
**Priority**: {priority}
**Status**: pending
**Area**: {area}

### Requested Capability
{request}
{ctx_str}

### Complexity Estimate
{complexity}

### Suggested Implementation
<!-- TODO: fill in implementation plan if known -->

### Metadata
- **Frequency**: {frequency}{related_str}

---
"""
        return self._append("FEATURE_REQUESTS.md", entry.strip())
    
    # ─── RESOLUTION & PROMOTION ────────────────────────────────────────────────
    
    def resolve(self, entry_id: str, resolution: str, notes: str = "") -> bool:
        now = _datetime.now().isoformat()
        resolution_block = f"""
### Resolution
- **Resolved**: {now}
- **Action**: {resolution}
- **Notes**: {notes}
"""
        for fname in ["LEARNINGS.md", "ERRORS.md", "FEATURE_REQUESTS.md"]:
            path = self.learnings_dir / fname
            if not path.exists():
                continue
            content = path.read_text()
            if entry_id not in content:
                continue
            lines = content.splitlines()
            entry_start = next((i for i, line in enumerate(lines) if entry_id in line), None)
            if entry_start is None:
                continue
            entry_end = next((i for i in range(entry_start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
            insert_pos = next((i for i in range(entry_start, entry_end) if lines[i].strip() == "---"), entry_end)
            lines.insert(insert_pos, resolution_block)
            for i in range(entry_start, insert_pos):
                if lines[i].startswith("**Status**:"):
                    lines[i] = "**Status**: resolved"
                    break
            path.write_text("\n".join(lines))
            return True
        return False
    
    def promote_to_dna(self, entry_id: str, distillate: str) -> bool:
        now = _datetime.now().isoformat()
        dna_path = self.learnings_dir / "DNA_UPDATES.md"
        entry = f"""
## [{entry_id}] {_datetime.now().strftime("%Y-%m-%d")}

**Promoted**: {now}
**Source**: .learnings/

### Distillate
{distillate}

---
"""
        self._append_to_file(dna_path, entry.strip())
        return self.resolve(entry_id, "promoted", "Elevated to DNA_UPDATES.md")
    
    # ─── QUERY API ──────────────────────────────────────────────────────────────
    
    def get_pending(self, area: _Optional[str] = None, limit: int = 50) -> _List[_Dict]:
        results = []
        id_pat = _re.compile(r"## \[(\w+-\d{8}-\d{3})\] (.+)")
        status_pat = _re.compile(r"\*\*Status\*\*: (\w+)")
        area_pat = _re.compile(r"\*\*Area\*\*: (\w+)")
        priority_pat = _re.compile(r"\*\*Priority\*\*: (\w+)")
        for fname in ["LEARNINGS.md", "ERRORS.md", "FEATURE_REQUESTS.md"]:
            path = self.learnings_dir / fname
            if not path.exists():
                continue
            for entry in path.read_text().split("---"):
                if not entry.strip():
                    continue
                id_m = id_pat.search(entry)
                if not id_m:
                    continue
                entry_id = id_m.group(1)
                title = id_m.group(2)
                status = status_pat.search(entry)
                e_area = area_pat.search(entry)
                priority = priority_pat.search(entry)
                s = status.group(1) if status else "unknown"
                if s != "pending":
                    continue
                ea = e_area.group(1) if e_area else "unknown"
                if area and ea != area:
                    continue
                results.append({
                    "id": entry_id, "title": title, "status": s,
                    "area": ea, "priority": priority.group(1) if priority else "medium",
                    "file": fname,
                })
                if len(results) >= limit:
                    break
        return results
    
    def get_stats(self) -> _Dict[str, _Any]:
        stats = {}
        id_pat = _re.compile(r"## \[(\w+)-\d{8}-\d{3}\]")
        status_pat = _re.compile(r"\*\*Status\*\*: (\w+)")
        priority_pat = _re.compile(r"\*\*Priority\*\*: (\w+)")
        for fname in ["LEARNINGS.md", "ERRORS.md", "FEATURE_REQUESTS.md"]:
            path = self.learnings_dir / fname
            if not path.exists():
                stats[fname] = {"total": 0, "pending": 0, "resolved": 0}
                continue
            entries = path.read_text().split("---")
            total = pending = resolved = 0
            critical = high = medium = low = 0
            for entry in entries:
                if not entry.strip() or not id_pat.search(entry):
                    continue
                total += 1
                s = status_pat.search(entry)
                p = priority_pat.search(entry)
                status = s.group(1) if s else "unknown"
                priority = p.group(1) if p else "medium"
                if status == "pending":
                    pending += 1
                elif status == "resolved":
                    resolved += 1
                if priority == "critical":
                    critical += 1
                elif priority == "high":
                    high += 1
                elif priority == "medium":
                    medium += 1
                elif priority == "low":
                    low += 1
            stats[fname] = {"total": total, "pending": pending, "resolved": resolved,
                            "critical": critical, "high": high, "medium": medium, "low": low}
        return stats
    
    # ─── INTERNAL ──────────────────────────────────────────────────────────────
    
    def _append(self, filename: str, entry: str) -> str:
        path = self.learnings_dir / filename
        self._append_to_file(path, entry)
        m = _re.search(r"## \[(\w+-\d{8}-\d{3})\]", entry)
        return m.group(1) if m else "UNKNOWN"
    
    def _append_to_file(self, path: _Path, content: str):
        with self._lock:
            with open(path, "a") as f:
                f.write("\n" + content + "\n")


# ─── SINGLETON ────────────────────────────────────────────────────────────────

_global_logger: _Optional[LearningLogger] = None


def get_learning_logger() -> LearningLogger:
    global _global_logger
    if _global_logger is None:
        _global_logger = LearningLogger()
    return _global_logger


# ─── CONVENIENCE SHORTCUTS ────────────────────────────────────────────────────

def log_error(summary: str, error_detail: str, **kwargs) -> str:
    return get_learning_logger().log_error(summary, error_detail, **kwargs)


def log_learning(category: str, summary: str, details: str, **kwargs) -> str:
    return get_learning_logger().log_learning(category, summary, details, **kwargs)


def log_correction(summary: str, what_was_wrong: str, what_is_correct: str, **kwargs) -> str:
    return get_learning_logger().log_correction(summary, what_was_wrong, what_is_correct, **kwargs)


def log_insight(summary: str, what_discovered: str, why_useful: str, **kwargs) -> str:
    return get_learning_logger().log_insight(summary, what_discovered, why_useful, **kwargs)


def log_knowledge_gap(summary: str, what_was_expected: str, what_actually_happened: str, **kwargs) -> str:
    return get_learning_logger().log_knowledge_gap(summary, what_was_expected, what_actually_happened, **kwargs)


def log_best_practice(summary: str, pattern: str, when_to_use: str, **kwargs) -> str:
    return get_learning_logger().log_best_practice(summary, pattern, when_to_use, **kwargs)


def log_feature_request(capability: str, request: str, **kwargs) -> str:
    return get_learning_logger().log_feature_request(capability, request, **kwargs)


def get_pending(area: _Optional[str] = None, limit: int = 50) -> _List[_Dict]:
    return get_learning_logger().get_pending(area, limit)


def get_learning_stats() -> _Dict[str, _Any]:
    return get_learning_logger().get_stats()


if __name__ == "__main__":
    _logging.basicConfig(level=_logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logger = get_learning_logger()
    eid = logger.log_insight(
        "Self-improvement v2 system initialized",
        "LearningLogger + SelfImprovementEngine both available from single import",
        "Enables unified access: file-based learnings + event-based optimization",
        source="self_audit", area="memory", tags=["initialization", "self-improvement"],
    )
    print(f"Logged insight: {eid}")
    print(_json.dumps(logger.get_stats(), indent=2))
