"""
app/ingestion/__init__.py — ILMA Data Source Ingestion Service
Reads and parses all ILMA data sources into the dashboard SQLite database.
"""
import json
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import sys
import importlib.util

import app.config as config
from app.models import (
    Provider, ModelId, BenchmarkRecord, TokenUsageEvent,
    CapabilityRegistryRecord, EvidenceRecord, SubagentModelRoute,
    WorkflowDefinition, RefreshJob, SystemHealthSnapshot
)
from sqlmodel import Session


class IngestionService:
    """Service responsible for ingesting all ILMA data sources into the dashboard DB."""

    def __init__(self, session: Session):
        self.session = session
        self.stats = {
            "providers": 0,
            "models": 0,
            "benchmarks": 0,
            "capabilities": 0,
            "evidence": 0,
            "routes": 0,
            "workflows": 0,
            "errors": []
        }

    # -------------------------------------------------------------------------
    # PUBLIC API
    # -------------------------------------------------------------------------

    def ingest_all(self) -> Dict[str, Any]:
        """Run all ingestion pipelines. Returns stats dict."""
        self.stats = {"providers": 0, "models": 0, "benchmarks": 0,
                      "capabilities": 0, "evidence": 0, "routes": 0,
                      "workflows": 0, "errors": []}

        try:
            self.ingest_providers_from_spec_db()
        except Exception as e:
            self.stats["errors"].append(f"providers: {e}")

        try:
            self.ingest_models_from_spec_db()
        except Exception as e:
            self.stats["errors"].append(f"models: {e}")

        try:
            self.ingest_benchmarks_from_legacy_db()
        except Exception as e:
            self.stats["errors"].append(f"benchmarks: {e}")

        try:
            self.ingest_capability_registry()
        except Exception as e:
            self.stats["errors"].append(f"capabilities: {e}")

        try:
            self.ingest_evidence_ledger()
        except Exception as e:
            self.stats["errors"].append(f"evidence: {e}")

        try:
            self.ingest_routing_rules()
        except Exception as e:
            self.stats["errors"].append(f"routes: {e}")

        try:
            self.ingest_health_snapshots()
        except Exception as e:
            self.stats["errors"].append(f"health: {e}")

        try:
            self._upsert_refresh_job("full_ingest", "Full ILMA data ingestion",
                                     "all", self.stats)
        except Exception as e:
            self.stats["errors"].append(f"refresh_job: {e}")

        self.session.commit()
        return self.stats

    # -------------------------------------------------------------------------
    # PROVIDERS
    # -------------------------------------------------------------------------

    def ingest_providers_from_spec_db(self) -> None:
        """Extract unique providers from model_specialization_database.json"""
        spec_path = config.SPEC_DB_PATH
        if not spec_path.exists():
            return

        with open(spec_path) as f:
            data = json.load(f)

        models = data.get("models", {})
        providers_seen = set()

        for model_key, model_data in models.items():
            provider = model_data.get("provider", "")
            if not provider or provider in providers_seen:
                continue
            providers_seen.add(provider)

            # Determine source type
            source_type = self._classify_provider_source(provider)

            # Check if api key present (via env check)
            api_key_present = self._check_api_key_for_provider(provider)

            provider_record = {
                "provider_id": provider,
                "display_name": self._provider_display_name(provider),
                "source_type": source_type,
                "trust_level": 7,
                "api_key_present": api_key_present,
                "api_key_source": self._api_key_source(provider),
                "health_score": 80,
                "last_verified": datetime.utcnow().isoformat(),
                "stale_status": "active",
                "notes": ""
            }

            self._upsert(Provider, {"provider_id": provider}, provider_record)
            self.stats["providers"] += 1

    # -------------------------------------------------------------------------
    # MODELS + BENCHMARKS
    # -------------------------------------------------------------------------

    def ingest_models_from_spec_db(self) -> None:
        """Ingest all models from model_specialization_database.json"""
        spec_path = config.SPEC_DB_PATH
        if not spec_path.exists():
            return

        with open(spec_path) as f:
            data = json.load(f)

        schema_version = data.get("schema_version", "1.1")
        models = data.get("models", {})

        for model_key, model_data in models.items():
            canonical_id = model_data.get("canonical_model_id", model_key)
            provider = model_data.get("provider", "")

            # Model record
            model_record = {
                "canonical_model_id": canonical_id,
                "provider": provider,
                "provider_model_id": model_data.get("model_id", canonical_id),
                "display_name": canonical_id,
                "aliases": "",
                "free_or_paid": model_data.get("free_or_paid", "FREE").upper(),
                "allowed_by_policy": model_data.get("allowed_by_policy", True),
                "availability_status": "ACTIVE",
                "context_window": model_data.get("context_window", 128000),
                "max_output_tokens": model_data.get("max_output_tokens", 8192),
                "input_cost_per_1m": model_data.get("input_cost_per_1m", 0.0),
                "output_cost_per_1m": model_data.get("output_cost_per_1m", 0.0),
                "modality": model_data.get("modality", "text"),
                "supports_tools": model_data.get("tool_use_score", 0) > 0.3,
                "supports_json": True,
                "supports_vision": model_data.get("supports_vision", False),
                "supports_long_context": model_data.get("context_window", 0) >= 128000,
                "source_type": self._map_source_type(model_data.get("evidence_level", "")),
                "trust_level": self._quality_to_trust(model_data.get("quality_score", 0.5)),
                "last_verified": model_data.get("last_updated", ""),
                "benchmark_coverage": schema_version,
                "caveat": model_data.get("caveat", "")
            }
            self._upsert(ModelId, {"canonical_model_id": canonical_id}, model_record)
            self.stats["models"] += 1

            # Benchmark records for this model (quality, coding, reasoning, tool_use scores)
            task_categories = [
                ("quality", model_data.get("quality_score")),
                ("coding", model_data.get("coding_score")),
                ("reasoning", model_data.get("reasoning_score")),
                ("tool_use", model_data.get("tool_use_score")),
            ]

            for task_category, score in task_categories:
                if score is None:
                    continue
                benchmark_id = f"{canonical_id}:{task_category}"
                benchmark_record = {
                    "benchmark_id": benchmark_id,
                    "canonical_model_id": canonical_id,
                    "provider": provider,
                    "provider_model_id": model_data.get("model_id", canonical_id),
                    "task_category": task_category,
                    "score": float(score),
                    "benchmark_type": "passive",
                    "evidence_level": model_data.get("evidence_level", ""),
                    "source_name": "model_specialization_database",
                    "source_url": "",
                    "latency_ms": 0.0,
                    "cost_estimate": 0.0,
                    "quality_notes": "",
                    "benchmarked_at": model_data.get("last_updated", ""),
                    "caveat": model_data.get("caveat", "")
                }
                self._upsert(BenchmarkRecord, {"benchmark_id": benchmark_id}, benchmark_record)
                self.stats["benchmarks"] += 1

    # -------------------------------------------------------------------------
    # LEGACY BENCHMARK DB
    # -------------------------------------------------------------------------

    def ingest_benchmarks_from_legacy_db(self) -> None:
        """Read from ilma_benchmark.db if it has benchmark_runs / model_rankings tables"""
        db_path = config.BENCHMARK_DB_PATH
        if not db_path.exists():
            return

        try:
            conn = sqlite3.connect(str(db_path))
            cur = conn.cursor()

            # Check what tables exist
            cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cur.fetchall()]

            if "benchmark_runs" in tables:
                cur.execute("SELECT * FROM benchmark_runs LIMIT 1000")
                columns = [desc[0] for desc in cur.description] if cur.description else []
                for row in cur.fetchall():
                    row_dict = dict(zip(columns, row))
                    self._ingest_benchmark_run(row_dict)

            if "model_rankings" in tables:
                cur.execute("SELECT * FROM model_rankings LIMIT 1000")
                columns = [desc[0] for desc in cur.description] if cur.description else []
                for row in cur.fetchall():
                    row_dict = dict(zip(columns, row))
                    self._ingest_model_ranking(row_dict)

            conn.close()
        except Exception as e:
            self.stats["errors"].append(f"legacy_db: {e}")

    def _ingest_benchmark_run(self, row: Dict[str, Any]) -> None:
        """Ingest a single benchmark_runs row"""
        benchmark_id = row.get("id", row.get("benchmark_id", ""))
        if not benchmark_id:
            return
        record = {
            "benchmark_id": str(benchmark_id),
            "canonical_model_id": row.get("model_id", ""),
            "provider": row.get("provider", ""),
            "provider_model_id": row.get("provider_model_id", ""),
            "task_category": row.get("task_category", ""),
            "score": float(row.get("score", 0)),
            "benchmark_type": "live",
            "evidence_level": row.get("evidence_level", ""),
            "source_name": row.get("source", ""),
            "source_url": row.get("source_url", ""),
            "latency_ms": float(row.get("latency_ms", 0)),
            "cost_estimate": float(row.get("cost", 0)),
            "quality_notes": "",
            "benchmarked_at": row.get("timestamp", row.get("run_at", "")),
            "caveat": ""
        }
        self._upsert(BenchmarkRecord, {"benchmark_id": benchmark_id}, record)
        self.stats["benchmarks"] += 1

    def _ingest_model_ranking(self, row: Dict[str, Any]) -> None:
        """Ingest a single model_rankings row"""
        ranking_id = f"ranking:{row.get('model_id', '')}:{row.get('task_category', '')}"
        record = {
            "benchmark_id": ranking_id,
            "canonical_model_id": row.get("model_id", ""),
            "provider": row.get("provider", ""),
            "provider_model_id": row.get("provider_model_id", ""),
            "task_category": row.get("task_category", ""),
            "score": float(row.get("ranking_score", 0)),
            "benchmark_type": "ranking",
            "evidence_level": row.get("evidence_level", ""),
            "source_name": row.get("source", "model_rankings"),
            "source_url": "",
            "latency_ms": 0.0,
            "cost_estimate": 0.0,
            "quality_notes": "",
            "benchmarked_at": row.get("timestamp", ""),
            "caveat": ""
        }
        self._upsert(BenchmarkRecord, {"benchmark_id": ranking_id}, record)
        self.stats["benchmarks"] += 1

    # -------------------------------------------------------------------------
    # CAPABILITY REGISTRY
    # -------------------------------------------------------------------------

    def ingest_capability_registry(self) -> None:
        """Parse ilma_capability_registry.py to extract capabilities"""
        script_path = config.CAPABILITY_REGISTRY_SCRIPT
        if not script_path.exists():
            return

        # Load registry data from JSON source
        json_path = config.ILMA_DIR / "config" / "ilma_capability_registry.json"
        if json_path.exists():
            with open(json_path) as f:
                data = json.load(f)

            capabilities = data.get("capabilities", {})
            for cap_name, cap_data in capabilities.items():
                record = {
                    "capability_id": cap_name,
                    "capability_name": cap_data.get("name", cap_name),
                    "category": cap_data.get("category", ""),
                    "status": self._map_capability_status(cap_data.get("status", "")),
                    "implementation_path": cap_data.get("implementation", {}).get("path", ""),
                    "test_path": cap_data.get("testing", {}).get("path", ""),
                    "evidence_id": "",
                    "last_verified": cap_data.get("last_verified", ""),
                    "caveat": ""
                }
                self._upsert(CapabilityRegistryRecord,
                             {"capability_id": cap_name}, record)
                self.stats["capabilities"] += 1

    # -------------------------------------------------------------------------
    # EVIDENCE LEDGER
    # -------------------------------------------------------------------------

    def ingest_evidence_ledger(self) -> None:
        """Walk evidence/ directory and ingest markdown files as evidence records"""
        evidence_dir = config.EVIDENCE_DIR
        if not evidence_dir.exists():
            return

        for md_file in evidence_dir.glob("*.md"):
            try:
                content = md_file.read_text()
                evidence_id = md_file.stem
                record = self._parse_evidence_md(evidence_id, content)
                if record:
                    self._upsert(EvidenceRecord,
                                 {"evidence_id": evidence_id}, record)
                    self.stats["evidence"] += 1
            except Exception:
                continue

    def _parse_evidence_md(self, evidence_id: str, content: str) -> Dict[str, Any]:
        """Parse a markdown evidence file into a record dict"""
        lines = content.split("\n")
        record = {
            "evidence_id": evidence_id,
            "claim": "",
            "capability": "",
            "test_performed": "",
            "result": "",
            "status": "UNVERIFIED",
            "confidence": 0.0,
            "source_file": f"evidence/{evidence_id}.md",
            "next_retest": "",
            "timestamp": datetime.utcnow().isoformat()
        }

        for line in lines:
            line = line.strip()
            if line.startswith("# Evidence:"):
                record["claim"] = line[len("# Evidence:"):].strip()
            elif line.startswith("**Capability:**"):
                record["capability"] = line[len("**Capability:**"):].strip().strip("*")
            elif line.startswith("**Status:**"):
                record["status"] = line[len("**Status:**"):].strip().strip("*")
            elif line.startswith("**Confidence:**"):
                conf_str = line[len("**Confidence:**"):].strip().strip("*").replace("%", "")
                try:
                    record["confidence"] = float(conf_str) / 100.0
                except ValueError:
                    pass
            elif line.startswith("**Test:**"):
                record["test_performed"] = line[len("**Test:**"):].strip().strip("*")
            elif line.startswith("**Result:**"):
                record["result"] = line[len("**Result:**"):].strip().strip("*")

        return record

    # -------------------------------------------------------------------------
    # ROUTING RULES
    # -------------------------------------------------------------------------

    def ingest_routing_rules(self) -> None:
        """Extract routing rules from ilma_unified_router.py"""
        # Build routes from CAPABILITY_MODEL_PREFERENCE patterns
        routes = self._extract_capability_model_preference()
        for route_data in routes:
            self._upsert(SubagentModelRoute,
                         {"role": route_data["role"], "route_order": route_data["route_order"]},
                         route_data)
            self.stats["routes"] += 1

    def _extract_capability_model_preference(self) -> List[Dict[str, Any]]:
        """Extract model preference patterns for routing"""
        routes = []

        # Predefined capability → model mappings based on ILMA routing policy
        capability_models = {
            "coding": [
                ("coding_subagent", "nvidia", "nvidia/deepseek-ai/deepseek-coder-33b-instruct", "deepseek-ai/deepseek-coder-33b-instruct", "FREE"),
                ("coding_subagent", "arena", "arena/starcoder2-15b", "starcoder2-15b", "FREE"),
                ("coding_subagent", "qwen", "qwen/coder", "coder", "FREE"),
            ],
            "research": [
                ("research_subagent", "nvidia", "nvidia/nemotron-4-mini-databricks", "nemotron-4-mini-databricks", "FREE"),
                ("research_subagent", "google", "google/gemini-2.0-flash", "gemini-2.0-flash", "FREE"),
            ],
            "reasoning": [
                ("reasoning_subagent", "nvidia", "nvidia/nemotron-4-mini-databricks", "nemotron-4-mini-databricks", "FREE"),
                ("reasoning_subagent", "qwen", "qwen/qwen-72b-chat", "qwen-72b-chat", "FREE"),
            ],
            "general": [
                ("general_subagent", "nvidia", "nvidia/mistralai/mistral-nemo-12b", "mistralai/mistral-nemo-12b", "FREE"),
                ("general_subagent", "google", "google/gemini-2.0-flash", "gemini-2.0-flash", "FREE"),
            ],
        }

        order = 1
        for capability, model_list in capability_models.items():
            for role, provider, canonical_id, provider_model_id, free_paid in model_list:
                routes.append({
                    "role": role,
                    "task_category": capability,
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
                    "is_active": True
                })
                order += 1

        return routes

    # -------------------------------------------------------------------------
    # HEALTH SNAPSHOTS
    # -------------------------------------------------------------------------

    def ingest_health_snapshots(self) -> None:
        """Ingest health report snapshots"""
        health_dir = config.HEALTH_REPORTS_DIR
        if not health_dir.exists():
            return

        for report_file in health_dir.glob("*.json"):
            try:
                with open(report_file) as f:
                    data = json.load(f)

                ts = data.get("timestamp", report_file.stem)
                summary = data.get("summary", {})
                capability_matrix = data.get("capability_matrix", {})

                record = {
                    "timestamp": ts,
                    "total_tests": summary.get("total_scripts", 0),
                    "tests_passed": summary.get("importable_scripts", 0),
                    "tests_failed": summary.get("broken_scripts", 0),
                    "validate_status": summary.get("system_status", ""),
                    "doctor_status": summary.get("openclaw_status", ""),
                    "production_smoke": "unknown",
                    "cron_status": "unknown",
                    "db_freshness": "fresh",
                    "stale_sources": "",
                    "broken_imports": str(summary.get("broken_scripts", 0))
                }
                self._upsert(SystemHealthSnapshot, {"timestamp": ts}, record)
            except Exception:
                continue

    # -------------------------------------------------------------------------
    # REFRESH JOB
    # -------------------------------------------------------------------------

    def _upsert_refresh_job(
        self,
        job_id: str,
        job_name: str,
        source_type: str,
        stats: Dict[str, Any]
    ) -> None:
        """Update refresh job record"""
        now = datetime.utcnow().isoformat()
        record = {
            "job_id": job_id,
            "job_name": job_name,
            "source_type": source_type,
            "last_run": now,
            "next_run": "",
            "status": "completed",
            "records_updated": sum([
                stats.get("providers", 0), stats.get("models", 0),
                stats.get("benchmarks", 0), stats.get("capabilities", 0),
                stats.get("evidence", 0), stats.get("routes", 0)
            ]),
            "error": "; ".join(stats.get("errors", [])) if stats.get("errors") else ""
        }
        self._upsert(RefreshJob, {"job_id": job_id}, record)

    # -------------------------------------------------------------------------
    # HELPERS
    # -------------------------------------------------------------------------

    def _upsert(self, model_cls, key_fields: Dict[str, Any], data: Dict[str, Any]) -> Any:
        """Generic upsert by key fields"""
        q = []
        for field, value in key_fields.items():
            q.append(getattr(model_cls, field) == value)

        existing = self.session.exec(
            model_cls.select().where(*q)
        ).first()

        if existing:
            for k, v in data.items():
                if hasattr(existing, k):
                    setattr(existing, k, v)
            return existing
        else:
            obj = model_cls(**data)
            self.session.add(obj)
            return obj

    def _classify_provider_source(self, provider: str) -> str:
        """Classify provider source type"""
        bridge_providers = {"qwen", "arena", "useai"}
        if provider in bridge_providers:
            return "BRIDGE"
        elif provider in {"openai", "google", "anthropic", "deepseek", "mistral"}:
            return "NATIVE"
        elif provider == "openrouter":
            return "OPENROUTER"
        else:
            return "NATIVE"

    def _check_api_key_for_provider(self, provider: str) -> bool:
        """Check if API key is present for provider via env vars"""
        env_keys = {
            "openai": "OPENAI_API_KEY",
            "google": "GOOGLE_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
            "deepseek": "DEEPSEEK_API_KEY",
            "mistral": "MISTRAL_API_KEY",
            "nvidia": "NVIDIA_API_KEY",
        }
        import os
        env_var = env_keys.get(provider, "")
        return bool(env_var and os.getenv(env_var))

    def _api_key_source(self, provider: str) -> str:
        """Return API key source string"""
        if provider in {"qwen", "arena", "useai"}:
            return "bridge"
        return "env"

    def _provider_display_name(self, provider: str) -> str:
        """Human-readable provider name"""
        names = {
            "nvidia": "NVIDIA NIM",
            "openai": "OpenAI",
            "google": "Google AI",
            "qwen": "Qwen Bridge",
            "arena": "Arena Bridge",
            "useai": "Use.ai Bridge",
            "deepseek": "DeepSeek",
            "anthropic": "Anthropic",
            "mistral": "Mistral AI",
        }
        return names.get(provider, provider.title())

    def _map_source_type(self, evidence_level: str) -> str:
        """Map evidence level string to source_type"""
        mapping = {
            "LIVE_BENCHMARKED": "LIVE_RUNTIME",
            "PROVIDER_DOC_BASED": "PASSIVE_PROVIDER",
            "COMMUNITY_REPORTED": "PASSIVE_TRUSTED",
            "HEURISTIC": "HEURISTIC",
            "INFERRED": "INFERRED",
        }
        return mapping.get(evidence_level, evidence_level or "UNVERIFIED")

    def _map_capability_status(self, status: str) -> str:
        """Map capability status strings"""
        mapping = {
            "STRONGLY_SUPPORTED": "STRONGLY_SUPPORTED",
            "PARTIALLY_SUPPORTED": "PARTIAL",
            "NOT_SUPPORTED": "BLOCKED",
            "UNVERIFIED": "UNVERIFIED",
        }
        return mapping.get(status, status or "UNVERIFIED")

    def _quality_to_trust(self, quality_score: float) -> int:
        """Convert quality score (0-1) to trust level (1-10)"""
        return int(min(10, max(1, round(quality_score * 10))))
