"""Ingestion service — loads ILMA data sources into dashboard DB."""
import json
import os
import re
from datetime import datetime
from sqlmodel import Session, select
from app.database import engine
from app.models import (
    Provider, ModelRecord, BenchmarkRecord, TokenUsageEvent,
    CapabilityRecord, EvidenceRecord, SubagentRoute, WorkflowDefinition,
    RefreshJob, SystemHealthSnapshot,
)


class IngestionService:
    """Ingest all ILMA data sources into dashboard DB."""
    
    ILMA_DIR = "/root/.hermes/profiles/ilma"
    
    def ingest_all(self) -> dict:
        results = {}
        results["providers"] = self.ingest_providers()
        results["models"] = self.ingest_models_from_specialization()
        results["bridge_models"] = self.ingest_bridge_models()
        results["benchmarks"] = self.ingest_benchmarks()
        results["capabilities"] = self.ingest_capabilities()
        results["evidence"] = self.ingest_evidence()
        results["subagent_routes"] = self.ingest_subagent_routes()
        results["workflows"] = self.ingest_workflows()
        results["health"] = self.capture_health_snapshot()
        return results
    
    def ingest_providers(self) -> int:
        """Ingest all known providers."""
        providers = [
            # From model_specialization_database.json native providers
            Provider(provider_id="nvidia", display_name="NVIDIA NIM", source_type="NATIVE", trust_level=9, health_score=90, last_verified="2026-05-11"),
            Provider(provider_id="google", display_name="Google AI Studio", source_type="NATIVE", trust_level=8, health_score=85, last_verified="2026-05-11"),
            Provider(provider_id="deepseek", display_name="DeepSeek", source_type="NATIVE", trust_level=8, health_score=88, last_verified="2026-05-11"),
            Provider(provider_id="openai", display_name="OpenAI", source_type="NATIVE", trust_level=9, health_score=85, last_verified="2026-05-11"),
            Provider(provider_id="mistral", display_name="Mistral AI", source_type="NATIVE", trust_level=7, health_score=82, last_verified="2026-05-11"),
            Provider(provider_id="xai", display_name="xAI", source_type="NATIVE", trust_level=7, health_score=78, last_verified="2026-05-11"),
            Provider(provider_id="meta", display_name="Meta AI", source_type="NATIVE", trust_level=6, health_score=70, last_verified="2026-05-11"),
            Provider(provider_id="anthropic", display_name="Anthropic", source_type="NATIVE", trust_level=9, health_score=88, last_verified="2026-05-11"),
            
            Provider(provider_id="fireworks", display_name="Fireworks AI", source_type="NATIVE", trust_level=6, health_score=72, last_verified="2026-05-11"),
            Provider(provider_id="hyper", display_name="Hyper", source_type="NATIVE", trust_level=5, health_score=65, last_verified="2026-05-11"),
            Provider(provider_id="novita", display_name="Novita AI", source_type="NATIVE", trust_level=5, health_score=60, last_verified="2026-05-11"),
            # Bridge providers
            Provider(provider_id="qwen", display_name="Qwen Bridge", source_type="BRIDGE", trust_level=8, health_score=80, last_verified="2026-05-10", notes="Playwright-stealth bridge to Qwen web interface"),
            Provider(provider_id="useai", display_name="Use.ai Bridge", source_type="BRIDGE", trust_level=9, health_score=100, last_verified="2026-05-13", notes="Playwright-stealth bridge to Use.ai GPT-5"),
            Provider(provider_id="arena", display_name="Arena.ai Bridge", source_type="BRIDGE", trust_level=7, health_score=50, last_verified="2026-05-10", notes="Playwright-stealth bridge to Arena.ai"),
        ]
        count = 0
        with Session(engine) as s:
            for p in providers:
                existing = s.exec(select(Provider).where(Provider.provider_id == p.provider_id)).first()
                if not existing:
                    s.add(p)
                    count += 1
            s.commit()
        return count
    
    def ingest_models_from_specialization(self) -> int:
        """Load 1088 models from model_specialization_database.json."""
        path = f"{self.ILMA_DIR}/model_specialization_database.json"
        if not os.path.exists(path):
            return 0
        
        with open(path) as f:
            db = json.load(f)
        
        models_data = db.get("models", {})
        count = 0
        with Session(engine) as s:
            for model_id, m in models_data.items():
                # Check if already exists
                existing = s.exec(select(ModelRecord).where(ModelRecord.canonical_model_id == model_id)).first()
                if existing:
                    continue
                
                record = ModelRecord(
                    canonical_model_id=model_id,
                    provider=m.get("provider", ""),
                    provider_model_id=m.get("model_id", model_id),
                    display_name=m.get("model_id", model_id),
                    free_or_paid=m.get("free_or_paid", "FREE").upper(),
                    allowed_by_policy=m.get("allowed_by_policy", True),
                    availability_status="ACTIVE",
                    context_window=m.get("context_window", 0),
                    source_type=m.get("evidence_level", "PROVIDER_DOC_BASED"),
                    trust_level=7,
                    last_verified=db.get("last_updated", ""),
                    quality_score=m.get("quality_score", 0.0),
                    coding_score=m.get("coding_score", 0.0),
                    reasoning_score=m.get("reasoning_score", 0.0),
                    tool_use_score=m.get("tool_use_score", 0.0),
                    specialization=m.get("specialization", ""),
                    benchmark_coverage=",".join(m.get("best_for", [])),
                )
                s.add(record)
                count += 1
            s.commit()
        return count
    
    def ingest_bridge_models(self) -> int:
        """Load bridge models from ilma_model_registry.py."""
        try:
            import sys
            sys.path.insert(0, f"{self.ILMA_DIR}/scripts")
            from ilma_model_registry import BridgeModelLoader
            
            bridge_models = BridgeModelLoader.load_all_bridge_models()
            count = 0
            with Session(engine) as s:
                for provider, models in bridge_models.items():
                    for m in models:
                        existing = s.exec(select(ModelRecord).where(ModelRecord.canonical_model_id == m.full_id)).first()
                        if existing:
                            continue
                        record = ModelRecord(
                            canonical_model_id=m.full_id,
                            provider=m.provider,
                            provider_model_id=m.canonical_id,
                            display_name=m.canonical_id,
                            aliases=",".join(m.aliases) if hasattr(m, 'aliases') and m.aliases else "",
                            free_or_paid="FREE" if m.free else "PAID",
                            allowed_by_policy=True,
                            availability_status="ACTIVE",
                            context_window=m.context_window if hasattr(m, 'context_window') else 0,
                            source_type="LIVE_RUNTIME_BENCHMARKED",
                            trust_level=8,
                            last_verified="2026-05-13",
                            quality_score=m.quality_score if hasattr(m, 'quality_score') else 0.8,
                            benchmark_coverage=",".join(m.capabilities) if hasattr(m, 'capabilities') else "",
                        )
                        s.add(record)
                        count += 1
                s.commit()
            return count
        except Exception as e:
            return 0
    
    def ingest_benchmarks(self) -> int:
        """Ingest benchmarks from ilma_benchmark.db."""
        bench_db_path = f"{self.ILMA_DIR}/ilma_benchmark.db"
        if not os.path.exists(bench_db_path):
            return 0
        
        import sqlite3
        count = 0
        conn = sqlite3.connect(bench_db_path)
        cur = conn.cursor()
        
        try:
            cur.execute("SELECT model_id, capability, quality_score, latency_ms, cost, timestamp FROM benchmark_runs")
            rows = cur.fetchall()
            
            with Session(engine) as s:
                for row in rows:
                    model_id, capability, score, latency, cost, ts = row
                    bench_id = f"live_{model_id}_{capability}_{ts}"
                    existing = s.exec(select(BenchmarkRecord).where(BenchmarkRecord.benchmark_id == bench_id)).first()
                    if existing:
                        continue
                    
                    record = BenchmarkRecord(
                        benchmark_id=bench_id,
                        canonical_model_id=model_id,
                        provider=model_id.split("-")[0] if "-" in model_id else "unknown",
                        provider_model_id=model_id,
                        task_category=capability,
                        score=score,
                        benchmark_type="live",
                        evidence_level="LIVE_RUNTIME_BENCHMARKED",
                        source_name="ilma_benchmark.db",
                        latency_ms=latency,
                        cost_estimate=cost,
                        benchmarked_at=ts,
                    )
                    s.add(record)
                    count += 1
                s.commit()
        finally:
            conn.close()
        return count
    
    def ingest_capabilities(self) -> int:
        """Parse and ingest capabilities from ilma_capability_registry.py."""
        cap_path = f"{self.ILMA_DIR}/scripts/ilma_capability_registry.py"
        if not os.path.exists(cap_path):
            return 0
        
        count = 0
        with open(cap_path) as f:
            content = f.read()
        
        # Extract CAPABILITY_CATEGORIES
        cats = {}
        import re
        cat_match = re.search(r'CAPABILITY_CATEGORIES\s*=\s*\{([^}]+)\}', content, re.DOTALL)
        if cat_match:
            for line in cat_match.group(1).split('\n'):
                m = re.match(r'\s*["\'](\w+)["\']\s*:\s*["\']([^"\']+)["\']', line)
                if m:
                    cats[m.group(1)] = m.group(2)
        
        # Extract all capability names from capability_to_engines or similar
        caps_found = set()
        for match in re.finditer(r'["\']([a-z_]+)["\']\s*:', content):
            cap = match.group(1)
            if len(cap) > 3 and "_" in cap:
                caps_found.add(cap)
        
        with Session(engine) as s:
            for cap in sorted(caps_found):
                existing = s.exec(select(CapabilityRecord).where(CapabilityRecord.capability_id == cap)).first()
                if existing:
                    continue
                
                category = cats.get(cap.split("_")[0].upper(), "OPERATIONAL")
                record = CapabilityRecord(
                    capability_id=cap,
                    capability_name=cap.replace("_", " ").title(),
                    category=category,
                    status="UNVERIFIED",
                    last_verified="",
                    caveat="Ingested from capability registry — needs evidence verification",
                )
                s.add(record)
                count += 1
            s.commit()
        return count
    
    def ingest_evidence(self) -> int:
        """Parse evidence entries from markdown ledger."""
        path = f"{self.ILMA_DIR}/docs/ILMA_EVIDENCE_LEDGER_2026-05-07.md"
        if not os.path.exists(path):
            return 0
        
        count = 0
        with open(path) as f:
            content = f.read()
        
        # Find all evidence IDs (### E### format)
        import re
        ev_ids = re.findall(r'###\s+(E\d+)', content)
        
        with Session(engine) as s:
            for ev_id in ev_ids:
                existing = s.exec(select(EvidenceRecord).where(EvidenceRecord.evidence_id == ev_id)).first()
                if existing:
                    continue
                
                record = EvidenceRecord(
                    evidence_id=ev_id,
                    claim=f"Evidence record {ev_id}",
                    capability="",
                    test_performed="",
                    result="",
                    status="UNVERIFIED",
                    confidence=0.0,
                    timestamp="2026-05-07",
                    caveat="Ingested from ILMA_EVIDENCE_LEDGER_2026-05-07.md",
                )
                s.add(record)
                count += 1
            s.commit()
        return count
    
    def ingest_subagent_routes(self) -> int:
        """Build subagent routes from CAPABILITY_MODEL_PREFERENCE."""
        try:
            import sys
            sys.path.insert(0, f"{self.ILMA_DIR}/scripts")
            from ilma_model_registry import get_registry, CAPABILITY_MODEL_PREFERENCE
            
            reg = get_registry()
            count = 0
            with Session(engine) as s:
                for capability, preferences in CAPABILITY_MODEL_PREFERENCE.items():
                    route_order = 0
                    for pref_id in preferences[:5]:  # max 5 routes
                        parts = pref_id.split("-", 1)
                        provider = parts[0] if len(parts) > 1 else pref_id
                        model_id = parts[1] if len(parts) > 1 else pref_id
                        
                        # Check if model exists in registry
                        m = reg.get_model(model_id, provider) if provider in ["qwen","useai","arena"] else reg.get_model(pref_id)
                        
                        record = SubagentRoute(
                            role=f"{capability}_subagent",
                            task_category=capability,
                            route_order=route_order + 1,
                            provider=provider,
                            canonical_model_id=pref_id,
                            provider_model_id=model_id,
                            free_or_paid="FREE",
                            route_score=0.8 if route_order == 0 else 0.6 - (route_order * 0.1),
                            specialization_score=m.quality_score if m and hasattr(m, 'quality_score') else 0.7,
                            benchmark_score=m.quality_score if m and hasattr(m, 'quality_score') else 0.7,
                            provider_trust=8,
                            fallback_reason="Primary" if route_order == 0 else f"Fallback #{route_order}",
                            is_active=True,
                        )
                        
                        existing = s.exec(select(SubagentRoute).where(
                            SubagentRoute.role == record.role,
                            SubagentRoute.route_order == record.route_order,
                        )).first()
                        if not existing:
                            s.add(record)
                            count += 1
                        route_order += 1
                s.commit()
            return count
        except Exception:
            return 0
    
    def ingest_workflows(self) -> int:
        """Ingest workflow definitions."""
        workflows = [
            WorkflowDefinition(
                workflow_id="ecc_workflow",
                workflow_name="ECC Workflow (8-Step Pipeline)",
                trigger="Bos command via ilma.py run",
                pipeline_stages='["4W1H_Analysis","ECC_Mapping","Security_Gate","Rules_Engine","Hook_Engine","Workflow_Executor","Verification","Report"]',
                tools_used='["runtime_router","tool_selector","lesson_memory","actor","judge_v4","reflexion","evidence_update","checkpoint","trace_export","report_generator"]',
                subagent_roles="task_actor,judge_critic,reflexion_engine",
                model_routes="useai-gpt-5 primary, qwen-qwen3.5-plus fallback",
                evidence_outputs="trace_json,final_markdown_report",
                status="ACTIVE",
            ),
            WorkflowDefinition(
                workflow_id="search_pipeline",
                workflow_name="Search & Research Pipeline",
                trigger="research task or search intent",
                pipeline_stages='["intent_detection","provider_selection","search_execution","result_synthesis","fact_check"]',
                tools_used='["felo_free","unified_router","evidence_checker"]',
                subagent_roles="search_agent,research_agent",
                model_routes="useai-gpt-5 primary, qwen fallback",
                evidence_outputs="search_results,citations",
                status="ACTIVE",
            ),
            WorkflowDefinition(
                workflow_id="benchmark_pipeline",
                workflow_name="Benchmark Refresh Pipeline",
                trigger="cron (every 6h) or manual refresh",
                pipeline_stages='["source_check","openrouter_refresh","nvidia_nim_refresh","benchmark_db_update","leaderboard_update"]',
                tools_used='["ilma_benchmark_db","ilma_model_registry","health_monitor"]',
                subagent_roles="benchmark_agent",
                model_routes="useai-gpt-5 for test evaluation",
                evidence_outputs="benchmark_records,leaderboard",
                status="ACTIVE",
            ),
        ]
        count = 0
        with Session(engine) as s:
            for w in workflows:
                existing = s.exec(select(WorkflowDefinition).where(WorkflowDefinition.workflow_id == w.workflow_id)).first()
                if not existing:
                    s.add(w)
                    count += 1
            s.commit()
        return count
    
    def capture_health_snapshot(self) -> bool:
        """Run ilma.py validate and doctor, store results."""
        import subprocess
        
        results = {
            "validate": "UNKNOWN",
            "doctor": "UNKNOWN",
            "tests": "0/0",
            "smoke": "NOT_RUN",
        }
        
        try:
            r1 = subprocess.run(
                ["python3", f"{self.ILMA_DIR}/scripts/ilma.py", "validate"],
                capture_output=True, text=True, timeout=60
            )
            results["validate"] = "PASS" if r1.returncode == 0 else f"FAIL ({r1.stderr[:100]})"
        except Exception as e:
            results["validate"] = f"ERROR: {e}"
        
        try:
            r2 = subprocess.run(
                ["python3", f"{self.ILMA_DIR}/scripts/ilma.py", "doctor"],
                capture_output=True, text=True, timeout=60
            )
            results["doctor"] = "PASS" if r2.returncode == 0 else f"FAIL ({r2.stderr[:100]})"
        except Exception as e:
            results["doctor"] = f"ERROR: {e}"
        
        now = datetime.now().isoformat()
        with Session(engine) as s:
            # Clear old snapshots, keep latest
            old = s.exec(select(SystemHealthSnapshot)).all()
            for o in old:
                s.delete(o)
            
            snap = SystemHealthSnapshot(
                timestamp=now,
                total_tests=0,
                tests_passed=0,
                validate_status=results["validate"],
                doctor_status=results["doctor"],
                production_smoke=results["smoke"],
                db_freshness=now,
            )
            s.add(snap)
            s.commit()
        return True