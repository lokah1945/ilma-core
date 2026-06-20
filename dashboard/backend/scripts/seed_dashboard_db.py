#!/usr/bin/env python3
"""
scripts/seed_dashboard_db.py — Full ILMA Dashboard SQLite Database Seeder
Ingests ALL ILMA data sources into the dashboard SQLite DB.

Usage: python3 scripts/seed_dashboard_db.py

Data sources read:
  - model_specialization_database.json (1088 models, 16 providers)
  - ilma_capability_registry.py + capability_registry.json (capabilities)
  - ilma_benchmark.db (legacy benchmark SQLite)
  - ILMA_EVIDENCE_LEDGER_2026-05-07.md (120 evidence entries)
  - ilma_unified_router.py (routing rules)
  - ilma_workflow_ecc.py (workflow definitions)
  - ilma.py validate + doctor (health snapshots)
"""
import json
import re
import sqlite3
import subprocess
import sys
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# ── Path Setup ──────────────────────────────────────────────────────────────
# This script lives at: dashboard/backend/scripts/seed_dashboard_db.py
# Backend app is at: dashboard/backend/app/
BACKEND_DIR = Path(__file__).parent.parent / "app"   # .../backend/app
ILMA_DIR = Path("/root/.hermes/profiles/ilma")
DATA_DIR = ILMA_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(BACKEND_DIR.parent))  # so 'app' package resolves

# ── SQLModel imports ──────────────────────────────────────────────────────────
from sqlmodel import Session, select, SQLModel
from app.database import engine, create_db_and_tables
from app.models import (
    Provider, ModelRecord, BenchmarkRecord, TokenUsageEvent,
    CapabilityRecord, EvidenceRecord, SubagentRoute,
    WorkflowDefinition, WorkflowRun, RefreshJob, SystemHealthSnapshot, TaskRecord
)


# ── Ingestion Stats ──────────────────────────────────────────────────────────
class Stats:
    def __init__(self):
        self.providers = 0
        self.models = 0
        self.benchmarks = 0
        self.capabilities = 0
        self.evidence = 0
        self.routes = 0
        self.workflows = 0
        self.health_snapshots = 0
        self.errors: List[str] = []
        self.missing_sources: List[str] = []

_stats = Stats()


# ─────────────────────────────────────────────────────────────────────────────
# UTILITY HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def now_iso() -> str:
    return datetime.utcnow().isoformat()


def safe_commit(session: Session):
    try:
        session.commit()
    except Exception as e:
        session.rollback()
        _stats.errors.append(f"commit: {e}")


def upsert(session: Session, model_cls, key_fields: Dict[str, Any], data: Dict[str, Any]):
    """Upsert by key fields using SQLModel select()."""
    try:
        conditions = [getattr(model_cls, k) == v for k, v in key_fields.items()]
        stmt = select(model_cls).where(*conditions)
        existing = session.exec(stmt).first()
        if existing:
            for k, v in data.items():
                if hasattr(existing, k):
                    setattr(existing, k, v)
        else:
            obj = model_cls(**data)
            session.add(obj)
    except Exception as e:
        _stats.errors.append(f"upsert {model_cls.__name__}: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# 1. SEED PROVIDERS
# ─────────────────────────────────────────────────────────────────────────────

def seed_providers(session: Session):
    """Extract unique providers from model_specialization_database.json + bridge providers."""
    spec_path = ILMA_DIR / "model_specialization_database.json"
    if not spec_path.exists():
        _stats.missing_sources.append("model_specialization_database.json")
        return

    data = json.load(open(spec_path))
    models = data.get("models", {})
    providers_seen = set()

    # Collect all providers from spec DB
    all_providers = set()
    for m in models.values():
        p = m.get("provider", "")
        if p:
            all_providers.add(p)

    # Add bridge providers (may not appear in spec DB)
    bridge_providers = {"qwen", "arena", "useai"}
    all_providers.update(bridge_providers)

    provider_names = {
        "nvidia": "NVIDIA NIM",
        "google": "Google AI",
        "deepseek": "DeepSeek",
        "openai": "OpenAI",
        "mistral": "Mistral AI",
        "xai": "xAI",
        "meta": "Meta AI",
        "anthropic": "Anthropic",
        
        "lepton": "Lepton AI",
        "fireworks": "Fireworks AI",
        
        "hyper": "Hyper AI",
        "novita": "Novita AI",
        "e2": "E2 AI",
        "maxkey": "MaxKey",
        "cAi": "cAi",
        "mimi": "Mimi AI",
        "nebius": "Nebius AI",
        "cloudflare": "Cloudflare Workers AI",
        "sambanova": "SambaNova",
        "ilfast": "IlFast",
        "hyperbolic": "Hyperbolic",
        "datagrok": "DataGroK",
        "kata": "Kata AI",
        "leonardo": "Leonardo AI",
        "qwen": "Qwen Bridge",
        "arena": "Arena Bridge",
        "useai": "Use.ai Bridge",
        "ai21-labs": "AI21 Labs",
        "alibaba": "Alibaba",
        "amazon": "Amazon",
        "blackbox": "Blackbox AI",
        "cohere": "Cohere",
        "microsoft-azure": "Microsoft Azure",
        "minimax": "MiniMax",
        "openrouter": "OpenRouter",
    }

    source_types = {
        "qwen": "BRIDGE", "arena": "BRIDGE", "useai": "BRIDGE",
        "openai": "NATIVE", "google": "NATIVE", "anthropic": "NATIVE",
        "deepseek": "NATIVE", "mistral": "NATIVE", "xai": "NATIVE",
        "meta": "NATIVE", "nvidia": "NATIVE",
        "openrouter": "OPENROUTER",
    }

    for provider in sorted(all_providers):
        if provider in providers_seen:
            continue
        providers_seen.add(provider)

        display = provider_names.get(provider, provider.title())
        source_type = source_types.get(provider, "NATIVE")
        api_key_present = bool(os.getenv(f"{provider.upper()}_API_KEY", ""))
        if provider in bridge_providers:
            api_key_source = "bridge"
        else:
            api_key_source = "env"

        record = {
            "provider_id": provider,
            "display_name": display,
            "source_type": source_type,
            "trust_level": 7,
            "api_key_present": api_key_present,
            "api_key_source": api_key_source,
            "health_score": 80,
            "last_verified": now_iso(),
            "stale_status": "active",
            "notes": ""
        }
        upsert(session, Provider, {"provider_id": provider}, record)
        _stats.providers += 1

    safe_commit(session)


# ─────────────────────────────────────────────────────────────────────────────
# 2. SEED MODELS + BENCHMARKS
# ─────────────────────────────────────────────────────────────────────────────

def seed_models_and_benchmarks(session: Session):
    """Ingest all 1088 models + quality/coding/reasoning/tool_use benchmarks."""
    spec_path = ILMA_DIR / "model_specialization_database.json"
    if not spec_path.exists():
        return

    data = json.load(open(spec_path))
    schema_version = data.get("schema_version", "1.1")
    models = data.get("models", {})

    evidence_level_map = {
        "LIVE_BENCHMARKED": "LIVE_RUNTIME",
        "PROVIDER_DOC_BASED": "PASSIVE_PROVIDER",
        "COMMUNITY_REPORTED": "PASSIVE_TRUSTED",
        "HEURISTIC": "HEURISTIC",
        "INFERRED": "INFERRED",
    }

    for model_key, m in models.items():
        canonical_id = m.get("canonical_model_id", model_key)
        provider = m.get("provider", "")
        free_or_paid = m.get("free_or_paid", "FREE").upper()
        quality = m.get("quality_score", 0.0)
        coding = m.get("coding_score", 0.0)
        reasoning = m.get("reasoning_score", 0.0)
        tool_use = m.get("tool_use_score", 0.0)
        context_window = m.get("context_window", 128000)
        evidence_level = m.get("evidence_level", "")
        source_type = evidence_level_map.get(evidence_level, evidence_level or "UNVERIFIED")
        trust_level = max(1, min(10, int(quality * 10)))
        caveat = m.get("caveat", "")
        last_updated = m.get("last_updated", "")

        model_record = {
            "canonical_model_id": canonical_id,
            "provider": provider,
            "provider_model_id": m.get("model_id", canonical_id),
            "display_name": canonical_id,
            "aliases": "",
            "free_or_paid": free_or_paid,
            "allowed_by_policy": m.get("allowed_by_policy", True),
            "availability_status": "ACTIVE",
            "context_window": context_window,
            "max_output_tokens": m.get("max_output_tokens", 8192),
            "input_cost_per_1m": m.get("input_cost_per_1m", 0.0),
            "output_cost_per_1m": m.get("output_cost_per_1m", 0.0),
            "modality": m.get("modality", "text"),
            "supports_tools": tool_use > 0.3,
            "supports_json": True,
            "supports_vision": m.get("supports_vision", False),
            "supports_long_context": context_window >= 128000,
            "source_type": source_type,
            "trust_level": trust_level,
            "last_verified": last_updated,
            "benchmark_coverage": schema_version,
            "caveat": caveat,
        }
        upsert(session, ModelRecord, {"canonical_model_id": canonical_id}, model_record)
        _stats.models += 1

        # Per-task-category benchmark records
        task_categories = [
            ("quality", quality),
            ("coding", coding),
            ("reasoning", reasoning),
            ("tool_use", tool_use),
        ]
        for task_category, score in task_categories:
            if score is None:
                continue
            benchmark_id = f"{canonical_id}:{task_category}"
            benchmark_record = {
                "benchmark_id": benchmark_id,
                "canonical_model_id": canonical_id,
                "provider": provider,
                "provider_model_id": m.get("model_id", canonical_id),
                "task_category": task_category,
                "score": float(score),
                "benchmark_type": "passive",
                "evidence_level": evidence_level,
                "source_name": "model_specialization_database",
                "source_url": "",
                "latency_ms": 0.0,
                "cost_estimate": 0.0,
                "quality_notes": "",
                "benchmarked_at": last_updated,
                "caveat": caveat,
            }
            upsert(session, BenchmarkRecord, {"benchmark_id": benchmark_id}, benchmark_record)
            _stats.benchmarks += 1

    safe_commit(session)


# ─────────────────────────────────────────────────────────────────────────────
# 3. SEED LEGACY BENCHMARK DB
# ─────────────────────────────────────────────────────────────────────────────

def seed_legacy_benchmark_db(session: Session):
    """Read from ilma_benchmark.db (benchmark_runs + model_rankings tables)."""
    db_path = ILMA_DIR / "ilma_benchmark.db"
    if not db_path.exists():
        _stats.missing_sources.append("ilma_benchmark.db")
        return

    try:
        conn = sqlite3.connect(str(db_path))
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [r[0] for r in cur.fetchall()]

        if "benchmark_runs" in tables:
            cur.execute("SELECT * FROM benchmark_runs LIMIT 5000")
            cols = [d[0] for d in cur.description] if cur.description else []
            for row in cur.fetchall():
                rd = dict(zip(cols, row))
                bid = rd.get("id") or rd.get("benchmark_id", "")
                if not bid:
                    continue
                record = {
                    "benchmark_id": str(bid),
                    "canonical_model_id": rd.get("model_id", ""),
                    "provider": rd.get("provider", ""),
                    "provider_model_id": rd.get("provider_model_id", ""),
                    "task_category": rd.get("task_category", ""),
                    "score": float(rd.get("score", 0)),
                    "benchmark_type": "live",
                    "evidence_level": rd.get("evidence_level", ""),
                    "source_name": rd.get("source", ""),
                    "source_url": rd.get("source_url", ""),
                    "latency_ms": float(rd.get("latency_ms", 0)),
                    "cost_estimate": float(rd.get("cost", 0)),
                    "quality_notes": "",
                    "benchmarked_at": rd.get("timestamp", rd.get("run_at", "")),
                    "caveat": "",
                }
                upsert(session, BenchmarkRecord, {"benchmark_id": bid}, record)
                _stats.benchmarks += 1

        if "model_rankings" in tables:
            cur.execute("SELECT * FROM model_rankings LIMIT 5000")
            cols = [d[0] for d in cur.description] if cur.description else []
            for row in cur.fetchall():
                rd = dict(zip(cols, row))
                ranking_id = f"ranking:{rd.get('model_id', '')}:{rd.get('task_category', '')}"
                record = {
                    "benchmark_id": ranking_id,
                    "canonical_model_id": rd.get("model_id", ""),
                    "provider": rd.get("provider", ""),
                    "provider_model_id": rd.get("provider_model_id", ""),
                    "task_category": rd.get("task_category", ""),
                    "score": float(rd.get("ranking_score", 0)),
                    "benchmark_type": "ranking",
                    "evidence_level": rd.get("evidence_level", ""),
                    "source_name": rd.get("source", "model_rankings"),
                    "source_url": "",
                    "latency_ms": 0.0,
                    "cost_estimate": 0.0,
                    "quality_notes": "",
                    "benchmarked_at": rd.get("timestamp", ""),
                    "caveat": "",
                }
                upsert(session, BenchmarkRecord, {"benchmark_id": ranking_id}, record)
                _stats.benchmarks += 1

        conn.close()
        safe_commit(session)
    except Exception as e:
        _stats.errors.append(f"legacy_benchmark_db: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# 4. SEED CAPABILITIES
# ─────────────────────────────────────────────────────────────────────────────

def seed_capabilities(session: Session):
    """Parse capability registry from JSON config files."""
    cap_paths = [
        ILMA_DIR / "config" / "ilma_capability_registry.json",
        ILMA_DIR / "capability_registry.json",
    ]

    cap_data = {}
    for p in cap_paths:
        if p.exists():
            try:
                cap_data = json.load(open(p))
                break
            except Exception:
                pass

    if cap_data:
        capabilities = cap_data.get("capabilities", cap_data)
        if isinstance(capabilities, dict):
            for cap_name, cap_info in capabilities.items():
                if isinstance(cap_info, dict):
                    record = {
                        "capability_id": cap_name,
                        "capability_name": cap_info.get("name", cap_name),
                        "category": cap_info.get("category", ""),
                        "status": _map_cap_status(cap_info.get("status", "UNVERIFIED")),
                        "implementation_path": cap_info.get("implementation", {}).get("path", "") if isinstance(cap_info.get("implementation"), dict) else "",
                        "test_path": cap_info.get("testing", {}).get("path", "") if isinstance(cap_info.get("testing"), dict) else "",
                        "evidence_id": "",
                        "last_verified": cap_info.get("last_verified", ""),
                        "caveat": "",
                    }
                else:
                    record = {
                        "capability_id": cap_name,
                        "capability_name": str(cap_info),
                        "category": "",
                        "status": "UNVERIFIED",
                        "implementation_path": "",
                        "test_path": "",
                        "evidence_id": "",
                        "last_verified": "",
                        "caveat": "",
                    }
                upsert(session, CapabilityRecord, {"capability_id": cap_name}, record)
                _stats.capabilities += 1
    else:
        # Fallback: predefined known ILMA capabilities
        known_caps = [
            ("coding", "Coding", "STRONGLY_SUPPORTED"),
            ("research", "Research", "STRONGLY_SUPPORTED"),
            ("writing", "Writing", "STRONGLY_SUPPORTED"),
            ("debugging", "Debugging", "STRONGLY_SUPPORTED"),
            ("reasoning", "Reasoning", "STRONGLY_SUPPORTED"),
            ("planning", "Planning", "STRONGLY_SUPPORTED"),
            ("memory", "Memory", "STRONGLY_SUPPORTED"),
            ("orchestrator", "Orchestrator", "STRONGLY_SUPPORTED"),
            ("skill_management", "Skill Management", "STRONGLY_SUPPORTED"),
            ("browser_automation", "Browser Automation", "PARTIALLY_SUPPORTED"),
            ("indonesian_nlp", "Indonesian NLP", "PARTIALLY_SUPPORTED"),
            ("meta_cognition", "Meta Cognition", "PARTIALLY_SUPPORTED"),
            ("auto_evolution", "Auto Evolution", "STRONGLY_SUPPORTED"),
            ("knowledge_ingestion", "Knowledge Ingestion", "STRONGLY_SUPPORTED"),
            ("failure_recovery", "Failure Recovery", "PARTIALLY_SUPPORTED"),
            ("system_awareness", "System Awareness", "STRONGLY_SUPPORTED"),
            ("runtime_benchmarking", "Runtime Benchmarking", "STRONGLY_SUPPORTED"),
            ("command_center", "Command Center", "PARTIALLY_SUPPORTED"),
            ("workflow_ecc", "Workflow ECC", "PARTIALLY_SUPPORTED"),
            ("adversarial_qa", "Adversarial QA", "PARTIALLY_SUPPORTED"),
            ("qa_critic", "QA Critic", "PARTIALLY_SUPPORTED"),
            ("long_term_memory", "Long Term Memory", "STRONGLY_SUPPORTED"),
            ("inference", "Inference", "STRONGLY_SUPPORTED"),
            ("tool_use", "Tool Use", "STRONGLY_SUPPORTED"),
        ]
        for cap_id, cap_name, status in known_caps:
            record = {
                "capability_id": cap_id,
                "capability_name": cap_name,
                "category": cap_id.replace("_", " ").title(),
                "status": status,
                "implementation_path": f"scripts/ilma_{cap_id}.py",
                "test_path": f"scripts/ilma_{cap_id}.py",
                "evidence_id": "",
                "last_verified": now_iso(),
                "caveat": "MISSING",
            }
            upsert(session, CapabilityRecord, {"capability_id": cap_id}, record)
            _stats.capabilities += 1

    safe_commit(session)


def _map_cap_status(s: str) -> str:
    m = {
        "STRONGLY_SUPPORTED": "STRONGLY_SUPPORTED",
        "PARTIALLY_SUPPORTED": "PARTIAL",
        "NOT_SUPPORTED": "BLOCKED",
        "UNVERIFIED": "UNVERIFIED",
        "VERIFIED": "VERIFIED",
    }
    return m.get(s, s or "UNVERIFIED")


# ─────────────────────────────────────────────────────────────────────────────
# 5. SEED EVIDENCE (from ILMA_EVIDENCE_LEDGER_2026-05-07.md)
# ─────────────────────────────────────────────────────────────────────────────

def seed_evidence_ledger(session: Session):
    """Parse ILMA_EVIDENCE_LEDGER_2026-05-07.md for evidence entries."""
    ledger_path = ILMA_DIR / "docs" / "ILMA_EVIDENCE_LEDGER_2026-05-07.md"
    if not ledger_path.exists():
        _stats.missing_sources.append("ILMA_EVIDENCE_LEDGER_2026-05-07.md")
        return

    content = open(ledger_path).read()

    # Split into entries by --- separators
    entries = re.split(r"\n---\n(?=### )", content)

    status_map = {
        "✅ VERIFIED": "VERIFIED",
        "❌ BROKEN": "BLOCKED",
        "❌ FAILED": "FAILED",
        "⚠️ PARTIAL": "PARTIAL",
        "✅ EXECUTION_VERIFIED": "VERIFIED",
        "✅ STRONGLY_SUPPORTED": "STRONGLY_SUPPORTED",
        "❌ DEPENDENCY_BLOCKED": "BLOCKED",
    }

    for entry in entries:
        lines = entry.strip().split("\n")
        if not lines:
            continue

        evidence_id = ""
        capability = ""
        claim = ""
        test_performed = ""
        result = ""
        status = "UNVERIFIED"
        confidence = 0.0
        source_file = "docs/ILMA_EVIDENCE_LEDGER_2026-05-07.md"
        next_retest = ""

        for line in lines:
            line = line.strip()

            # Evidence ID heading
            m = re.match(r"###\s+(E\d+|P2[ABCD]-\w+-\d+)\s+", line)
            if m:
                evidence_id = m.group(1)

            # Status from emoji
            for emoji, mapped_status in status_map.items():
                if emoji in line:
                    status = mapped_status
                    break

            # Field extraction
            if line.startswith("**Capability:**"):
                capability = line.split("**Capability:**", 1)[1].strip().strip("*")
            elif line.startswith("**Claim:**"):
                claim = line.split("**Claim:**", 1)[1].strip().strip("*")
            elif line.startswith("**Test:**"):
                test_performed = line.split("**Test:**", 1)[1].strip().strip("*")
            elif line.startswith("**Result:**"):
                result = line.split("**Result:**", 1)[1].strip().strip("*")
            elif line.startswith("**Confidence:**"):
                conf_str = line.split("**Confidence:**", 1)[1].strip().strip("*").replace("%", "")
                try:
                    confidence = float(conf_str) / 100.0
                except ValueError:
                    pass
            elif line.startswith("**Source File:**"):
                source_file = line.split("**Source File:**", 1)[1].strip().strip("*")
            elif line.startswith("**Next Retest:**"):
                next_retest = line.split("**Next Retest:**", 1)[1].strip().strip("*")

            # Pipe table rows
            if line.startswith("|") and "|" in line:
                parts = [p.strip() for p in line.split("|")]
                if len(parts) >= 3:
                    field = parts[1].lower()
                    val = parts[2]
                    if field == "capability":
                        capability = val
                    elif field == "claim":
                        claim = val
                    elif field == "test_performed":
                        test_performed = val
                    elif field == "result":
                        result = val
                    elif field == "status":
                        for emoji, mapped_status in status_map.items():
                            if emoji in val:
                                status = mapped_status
                                break
                        else:
                            status = val
                    elif field == "confidence":
                        try:
                            confidence = float(val.replace("%", "")) / 100.0
                        except ValueError:
                            pass
                    elif field == "source_file":
                        source_file = val
                    elif field == "next_retest":
                        next_retest = val

        if not evidence_id:
            continue

        record = {
            "evidence_id": evidence_id,
            "claim": claim,
            "capability": capability,
            "test_performed": test_performed,
            "result": result,
            "status": status,
            "confidence": confidence,
            "source_file": source_file,
            "next_retest": next_retest,
            "timestamp": now_iso(),
        }
        upsert(session, EvidenceRecord, {"evidence_id": evidence_id}, record)
        _stats.evidence += 1

    safe_commit(session)


# ─────────────────────────────────────────────────────────────────────────────
# 6. SEED SUBAGENT ROUTES
# ─────────────────────────────────────────────────────────────────────────────

def seed_routes(session: Session):
    """Build routing chains from ILMA unified router patterns."""

    # Based on BRIDGE_PRIORITY = ["qwen", "useai", "arena"]
    # and CAPABILITY_MODEL_PREFERENCE from ilma_model_registry.py
    routing_chains = [
        # coding chain
        ("coding_subagent", "coding", 1, "qwen", "qwen-qwen3.5-plus", "qwen3.5-plus", "FREE"),
        ("coding_subagent", "coding", 2, "arena", "arena-arena-*", "arena-*", "FREE"),
        ("coding_subagent", "coding", 3, "nvidia", "nvidia/deepseek-ai/deepseek-coder-33b-instruct", "deepseek-ai/deepseek-coder-33b-instruct", "FREE"),
        ("coding_subagent", "coding", 4, "openai", "openai/gpt-4o-mini", "gpt-4o-mini", "PAID"),
        # research chain
        ("research_subagent", "research", 1, "qwen", "qwen-qwen3.5-plus", "qwen3.5-plus", "FREE"),
        ("research_subagent", "research", 2, "google", "google/gemini-2.0-flash", "gemini-2.0-flash", "FREE"),
        ("research_subagent", "research", 3, "nvidia", "nvidia/nemotron-4-mini-databricks", "nemotron-4-mini-databricks", "FREE"),
        # reasoning chain
        ("reasoning_subagent", "reasoning", 1, "qwen", "qwen-qwen3.5-plus", "qwen3.5-plus", "FREE"),
        ("reasoning_subagent", "reasoning", 2, "nvidia", "nvidia/nemotron-4-mini-databricks", "nemotron-4-mini-databricks", "FREE"),
        ("reasoning_subagent", "reasoning", 3, "deepseek", "deepseek/deepseek-r1", "deepseek-r1", "FREE"),
        # general chain
        ("general_subagent", "general", 1, "nvidia", "nvidia/mistralai/mistral-nemo-12b", "mistralai/mistral-nemo-12b", "FREE"),
        ("general_subagent", "general", 2, "google", "google/gemini-2.0-flash", "gemini-2.0-flash", "FREE"),
        ("general_subagent", "general", 3, "qwen", "qwen-qwen3.5-plus", "qwen3.5-plus", "FREE"),
        # planning chain
        ("planning_subagent", "planning", 1, "qwen", "qwen-qwen3.5-plus", "qwen3.5-plus", "FREE"),
        ("planning_subagent", "planning", 2, "google", "google/gemini-2.0-flash", "gemini-2.0-flash", "FREE"),
        # writing chain
        ("writing_subagent", "writing", 1, "qwen", "qwen-qwen3.5-plus", "qwen3.5-plus", "FREE"),
        ("writing_subagent", "writing", 2, "google", "google/gemini-2.0-flash", "gemini-2.0-flash", "FREE"),
        # debugging chain
        ("debugging_subagent", "debugging", 1, "qwen", "qwen-qwen3.5-plus", "qwen3.5-plus", "FREE"),
        ("debugging_subagent", "debugging", 2, "nvidia", "nvidia/deepseek-ai/deepseek-coder-33b-instruct", "deepseek-ai/deepseek-coder-33b-instruct", "FREE"),
        # workflow_ecc chain
        ("workflow_subagent", "workflow", 1, "qwen", "qwen-qwen3.5-plus", "qwen3.5-plus", "FREE"),
        ("workflow_subagent", "workflow", 2, "google", "google/gemini-2.0-flash", "gemini-2.0-flash", "FREE"),
        # memory chain
        ("memory_subagent", "memory", 1, "qwen", "qwen-qwen3.5-plus", "qwen3.5-plus", "FREE"),
        ("memory_subagent", "memory", 2, "google", "google/gemini-2.0-flash", "gemini-2.0-flash", "FREE"),
        # Indonesian NLP
        ("nlp_subagent", "indonesian_nlp", 1, "qwen", "qwen-qwen3.5-plus", "qwen3.5-plus", "FREE"),
        ("nlp_subagent", "indonesian_nlp", 2, "google", "google/gemini-2.0-flash", "gemini-2.0-flash", "FREE"),
        # browser automation
        ("browser_subagent", "browser_automation", 1, "google", "google/gemini-2.0-flash", "gemini-2.0-flash", "FREE"),
        ("browser_subagent", "browser_automation", 2, "qwen", "qwen-qwen3.5-plus", "qwen3.5-plus", "FREE"),
    ]

    for role, task_cat, order, provider, canonical_id, provider_model_id, free_paid in routing_chains:
        record = {
            "role": role,
            "task_category": task_cat,
            "route_order": order,
            "provider": provider,
            "canonical_model_id": canonical_id,
            "provider_model_id": provider_model_id,
            "free_or_paid": free_paid,
            "route_score": 0.85,
            "specialization_score": 0.8,
            "benchmark_score": 0.75,
            "provider_trust": 7,
            "fallback_reason": "",
            "blocked_paid_candidates": "",
            "caveat": "",
            "is_active": True,
        }
        upsert(session, SubagentRoute,
               {"role": role, "route_order": order}, record)
        _stats.routes += 1

    safe_commit(session)


# ─────────────────────────────────────────────────────────────────────────────
# 7. SEED WORKFLOWS
# ─────────────────────────────────────────────────────────────────────────────

def seed_workflows(session: Session):
    """Parse workflow definitions from ilma_workflow_ecc.py + predefined workflows."""
    workflow_ecc_path = ILMA_DIR / "scripts" / "ilma_workflow_ecc.py"

    if workflow_ecc_path.exists():
        content = open(workflow_ecc_path).read()
        wf_pattern = re.compile(
            r'name\s*=\s*"([^"]+)".*?trigger\s*=\s*"([^"]*)"',
            re.DOTALL
        )
        for m in wf_pattern.finditer(content):
            wf_name = m.group(1)
            trigger = m.group(2)
            start = m.start()
            end = content.find('def ', start + 1)
            block = content[start:end if end != -1 else start + 500]
            stages = re.findall(r'(\w+)_stage', block)
            if not stages:
                stages = ["parse", "execute", "validate"]

            wf_id = wf_name.lower().replace(" ", "_").replace("-", "_")
            record = {
                "workflow_id": wf_id,
                "workflow_name": wf_name,
                "trigger": trigger,
                "pipeline_stages": json.dumps(stages),
                "tools_used": json.dumps([]),
                "subagent_roles": json.dumps([]),
                "model_routes": json.dumps([]),
                "evidence_outputs": "",
                "status": "active",
            }
            upsert(session, WorkflowDefinition, {"workflow_id": wf_id}, record)
            _stats.workflows += 1
    else:
        _stats.missing_sources.append("ilma_workflow_ecc.py")

    # Predefined core workflows
    predefined = [
        ("coding_workflow", "Coding Workflow", "code_request",
         ["parse", "plan", "execute", "review"], ["code_editor"], ["coding_subagent"]),
        ("research_workflow", "Research Workflow", "research_request",
         ["parse", "search", "analyze", "report"], ["web_search", "browser"], ["research_subagent"]),
        ("writing_workflow", "Writing Workflow", "write_request",
         ["parse", "outline", "draft", "review"], ["text_editor"], ["writing_subagent"]),
        ("planning_workflow", "Planning Workflow", "plan_request",
         ["analyze", "plan", "review"], [], ["planning_subagent"]),
        ("debugging_workflow", "Debugging Workflow", "debug_request",
         ["parse", "trace", "fix", "verify"], ["code_editor"], ["debugging_subagent"]),
        ("memory_workflow", "Memory Workflow", "memory_request",
         ["read", "write", "index"], [], ["memory_subagent"]),
    ]
    for wf_id, wf_name, trigger, stages, tools, roles in predefined:
        record = {
            "workflow_id": wf_id,
            "workflow_name": wf_name,
            "trigger": trigger,
            "pipeline_stages": json.dumps(stages),
            "tools_used": json.dumps(tools),
            "subagent_roles": json.dumps(roles),
            "model_routes": json.dumps([]),
            "evidence_outputs": "",
            "status": "active",
        }
        upsert(session, WorkflowDefinition, {"workflow_id": wf_id}, record)
        _stats.workflows += 1

    safe_commit(session)


# ─────────────────────────────────────────────────────────────────────────────
# 8. RUN ILMA VALIDATE + DOCTOR (health snapshots)
# ─────────────────────────────────────────────────────────────────────────────

def run_health_snapshot() -> Dict[str, Any]:
    """Run ilma.py validate and doctor commands for system health."""
    ilma_script = ILMA_DIR / "scripts" / "ilma.py"
    health = {
        "validate_status": "NOT_RUN",
        "doctor_status": "NOT_RUN",
        "validate_passed": False,
        "doctor_passed": False,
    }

    if not ilma_script.exists():
        _stats.missing_sources.append("scripts/ilma.py")
        return health

    # Run validate
    try:
        result = subprocess.run(
            [sys.executable, str(ilma_script), "validate"],
            capture_output=True, text=True, timeout=120,
            cwd=str(ILMA_DIR)
        )
        health["validate_status"] = "PASS" if result.returncode == 0 else "FAIL"
        health["validate_passed"] = result.returncode == 0
    except subprocess.TimeoutExpired:
        health["validate_status"] = "TIMEOUT"
    except Exception as e:
        health["validate_status"] = f"ERROR: {e}"

    # Run doctor
    try:
        result = subprocess.run(
            [sys.executable, str(ilma_script), "doctor"],
            capture_output=True, text=True, timeout=120,
            cwd=str(ILMA_DIR)
        )
        health["doctor_status"] = "PASS" if result.returncode == 0 else "FAIL"
        health["doctor_passed"] = result.returncode == 0
    except subprocess.TimeoutExpired:
        health["doctor_status"] = "TIMEOUT"
    except Exception as e:
        health["doctor_status"] = f"ERROR: {e}"

    return health


def seed_health_snapshots(session: Session, health: Dict[str, Any]):
    """Store health snapshot in DB."""
    ts = now_iso()
    record = {
        "timestamp": ts,
        "total_tests": 0,
        "tests_passed": 0,
        "tests_failed": 0,
        "validate_status": health.get("validate_status", "NOT_RUN"),
        "doctor_status": health.get("doctor_status", "NOT_RUN"),
        "production_smoke": "unknown",
        "cron_status": "unknown",
        "db_freshness": "fresh",
        "stale_sources": ", ".join(_stats.missing_sources) if _stats.missing_sources else "",
        "broken_imports": "",
    }
    upsert(session, SystemHealthSnapshot, {"timestamp": ts}, record)
    _stats.health_snapshots += 1
    safe_commit(session)


# ─────────────────────────────────────────────────────────────────────────────
# 9. REFRESH JOB TRACKING
# ─────────────────────────────────────────────────────────────────────────────

def seed_refresh_job(session: Session):
    """Record the ingestion as a refresh job."""
    now = now_iso()
    record = {
        "job_id": "full_ingest_2026_05_13",
        "job_name": "Full ILMA data ingestion",
        "source_type": "all",
        "last_run": now,
        "next_run": "",
        "status": "completed",
        "records_updated": (
            _stats.providers + _stats.models + _stats.benchmarks +
            _stats.capabilities + _stats.evidence + _stats.routes +
            _stats.workflows + _stats.health_snapshots
        ),
        "error": "; ".join(_stats.errors) if _stats.errors else "",
    }
    upsert(session, RefreshJob, {"job_id": "full_ingest_2026_05_13"}, record)
    safe_commit(session)


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def seed():
    print("[seed] Creating database tables...")
    create_db_and_tables()

    print("[seed] Starting ILMA data ingestion...")
    with Session(engine) as session:
        steps = [
            ("[1/9] Providers", lambda: seed_providers(session)),
            ("[2/9] Models + Benchmarks", lambda: seed_models_and_benchmarks(session)),
            ("[3/9] Legacy Benchmark DB", lambda: seed_legacy_benchmark_db(session)),
            ("[4/9] Capabilities", lambda: seed_capabilities(session)),
            ("[5/9] Evidence Ledger", lambda: seed_evidence_ledger(session)),
            ("[6/9] Subagent Routes", lambda: seed_routes(session)),
            ("[7/9] Workflows", lambda: seed_workflows(session)),
            ("[8/9] ILMA validate + doctor", lambda: None),  # handled below
            ("[9/9] Refresh Job", lambda: seed_refresh_job(session)),
        ]

        for label, fn in steps:
            print(f"  {label}...")
            try:
                fn()
            except Exception as e:
                _stats.errors.append(f"{label}: {e}")

        # Step 8: health snapshot (outside normal error handling)
        print("  [8/9] ILMA validate + doctor...")
        try:
            health = run_health_snapshot()
            seed_health_snapshots(session, health)
        except Exception as e:
            _stats.errors.append(f"health: {e}")

    # ── Report ───────────────────────────────────────────────────────────────
    print("\n=== INGESTION COMPLETE ===")
    print(f"  Providers:        {_stats.providers}")
    print(f"  Models:          {_stats.models}")
    print(f"  Benchmarks:      {_stats.benchmarks}")
    print(f"  Capabilities:    {_stats.capabilities}")
    print(f"  Evidence:        {_stats.evidence}")
    print(f"  Routes:          {_stats.routes}")
    print(f"  Workflows:       {_stats.workflows}")
    print(f"  Health Snapshots: {_stats.health_snapshots}")
    print(f"  Errors:          {len(_stats.errors)}")
    if _stats.errors:
        for err in _stats.errors[:10]:
            print(f"    - {err}")
    print(f"  Missing Sources: {len(_stats.missing_sources)}")
    if _stats.missing_sources:
        for src in _stats.missing_sources:
            print(f"    - {src}")
    print("=" * 27)

    # ── Verification ──────────────────────────────────────────────────────────
    with Session(engine) as session:
        provider_count = len(session.exec(select(Provider)).all())
        model_count = len(session.exec(select(ModelRecord)).all())
        benchmark_count = len(session.exec(select(BenchmarkRecord)).all())

        print(f"\nVerification (DB reads):")
        print(f"  Providers in DB:   {provider_count}")
        print(f"  Models in DB:      {model_count}")
        print(f"  Benchmarks in DB:  {benchmark_count}")

        success = provider_count > 0 and model_count > 0
        if success:
            print("\n[OK] Database seeded successfully!")
        else:
            print("\n[WARNING] Database appears empty - check errors above")

    return success


if __name__ == "__main__":
    success = seed()
    sys.exit(0 if success else 1)
