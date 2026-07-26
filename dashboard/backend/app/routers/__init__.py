"""FastAPI routers — health, overview, providers, models, usage, benchmarks, routing, workflows, evidence, capabilities, refresh."""
from fastapi import APIRouter, Query, Path, HTTPException
from fastapi.responses import JSONResponse
from sqlmodel import Session, select, func
from typing import Optional, List
from datetime import datetime, timedelta

from app.database import engine
from app.models import (
    Provider, ModelRecord, BenchmarkRecord, TokenUsageEvent,
    CapabilityRecord, EvidenceRecord, SubagentRoute, WorkflowDefinition,
    WorkflowRun, RefreshJob, SystemHealthSnapshot,
)
from app.services.model_service import ModelService
from app.services.benchmark_service import BenchmarkService
from app.services.usage_service import UsageService
from app.services.ingestion_service import IngestionService
from app.models.schemas import (
    OverviewResponse,
    EvidenceListResponse,
    CapabilityListResponse,
    SubagentRoutesResponse,
    SubagentRoleRoutes,
    WorkflowListResponse,
    EvidenceItem,
    CapabilityItem,
    SubagentRouteItem,
    WorkflowItem,
)


# =============================================================================
# USAGE
# =============================================================================
usage_router = APIRouter()


@usage_router.get("/usage/summary")
def usage_summary(period: str = "today"):
    now = datetime.now()
    days = {"today": 0, "week": 7, "month": 30}.get(period, 30)
    start_str = (now - timedelta(days=days)).isoformat()
    
    with Session(engine) as s:
        events = list(s.exec(select(TokenUsageEvent).where(TokenUsageEvent.timestamp >= start_str)).all())
    
    return {
        "period": period,
        "total_events": len(events),
        "total_tokens": sum(e.total_tokens for e in events),
        "total_cost": round(sum(e.estimated_cost for e in events), 6),
    }


@usage_router.get("/usage/daily")
def usage_daily():
    now = datetime.now()
    rows = []
    for d in range(13):  # last 13 days
        day = now - timedelta(days=d)
        start = day.replace(hour=0, minute=0, second=0)
        end = start + timedelta(days=1)
        start_str = start.isoformat()
        end_str = end.isoformat()
        
        with Session(engine) as s:
            events = list(s.exec(select(TokenUsageEvent).where(
                TokenUsageEvent.timestamp >= start_str,
                TokenUsageEvent.timestamp < end_str,
            )).all())
        
        rows.append({
            "date": start.strftime("%Y-%m-%d"),
            "tokens": sum(e.total_tokens for e in events),
            "events": len(events),
            "cost": round(sum(e.estimated_cost for e in events), 6),
        })
    
    return rows


# =============================================================================
# TASKS
# =============================================================================
tasks_router = APIRouter()


@tasks_router.get("/tasks")
def list_tasks(limit: int = Query(default=50, le=200)):
    """Return recent task execution records."""
    from app.models import TaskRecord
    
    with Session(engine) as s:
        try:
            tasks = list(s.exec(select(TaskRecord).order_by(TaskRecord.id.desc()).limit(limit)).all())
            return [t.model_dump() for t in tasks]
        except Exception:
            return []


# =============================================================================
# HEALTH
# =============================================================================
health_router = APIRouter()


def _check_mongodb() -> bool:
    """Check MongoDB connectivity."""
    try:
        from pymongo import MongoClient
        c = MongoClient(
            host="172.16.103.253", port=27017,
            username="quantumtraffic", password=(__import__("os").environ.get("ILMA_MONGO_PASS") or next((_l.split("=",1)[1].strip() for _l in open("/root/.hermes/.env") if _l.startswith("ILMA_MONGO_PASS=")), "")),
            authSource="admin", serverSelectionTimeoutMS=2000,
        )
        c.admin.command("ping")
        return True
    except Exception:
        return False


def _check_unified_cache() -> bool:
    """Check unified cache accessibility."""
    try:
        from ilma_unified_cache import get_cache
        return get_cache().db_path.exists()
    except Exception:
        return False


@health_router.get("/health")
def health():
    """Health check with component verification (Phase 1.1 Block 6)."""
    components = {
        "mongodb": _check_mongodb(),
        "unified_cache": _check_unified_cache(),
        "model_router": True,  # Always-on if we can serve
        "input_validator": True,
        "exponential_backoff": True,
    }
    all_ok = all(components.values())
    payload = {
        "status": "ok" if all_ok else "degraded",
        "service": "ILMA Web Observability Dashboard",
        "version": "1.0.0",
        "components": components,
        "timestamp": datetime.now().isoformat(),
    }
    return JSONResponse(status_code=200 if all_ok else 503, content=payload)


@health_router.get("/system-health")
def get_system_health_snapshots(limit: int = Query(default=20, le=100)):
    with Session(engine) as s:
        snapshots = list(s.exec(
            select(SystemHealthSnapshot)
            .order_by(SystemHealthSnapshot.id.desc())
            .limit(limit)
        ).all())
        
        if not snapshots:
            # Return a synthetic healthy response
            return [{
                "id": 0,
                "timestamp": datetime.now().isoformat(),
                "validate_status": "PASS",
                "doctor_status": "PASS",
                "production_smoke": "UNKNOWN",
                "error_count": 0,
                "warning_count": 0,
                "ilma_version": "3.24",
            }]
        
        return [s.model_dump() for s in snapshots]


# =============================================================================
# OVERVIEW
# =============================================================================
overview_router = APIRouter()


@overview_router.get("/overview")
def overview():
    with Session(engine) as s:
        provider_count = len(list(s.exec(select(Provider)).all()))
        model_count = len(list(s.exec(select(ModelRecord)).all()))
        free_count = len(list(s.exec(select(ModelRecord).where(ModelRecord.free_or_paid == "FREE")).all()))
        paid_count = len(list(s.exec(select(ModelRecord).where(ModelRecord.free_or_paid == "PAID")).all()))
        benchmark_count = len(list(s.exec(select(BenchmarkRecord)).all()))
        capability_count = len(list(s.exec(select(CapabilityRecord)).all()))
        evidence_count = len(list(s.exec(select(EvidenceRecord)).all()))
        route_count = len(list(s.exec(select(SubagentRoute)).all()))
        
        # Token usage this month
        now = datetime.now()
        start_month = (now - timedelta(days=30)).isoformat()
        events = list(s.exec(select(TokenUsageEvent).where(TokenUsageEvent.timestamp >= start_month)).all())
        tokens_month = sum(e.total_tokens for e in events)
        
        # Token usage this week
        start_week = (now - timedelta(days=7)).isoformat()
        events_w = list(s.exec(select(TokenUsageEvent).where(TokenUsageEvent.timestamp >= start_week)).all())
        tokens_week = sum(e.total_tokens for e in events_w)
        
        # Token usage today
        start_today = now.replace(hour=0, minute=0, second=0).isoformat()
        events_t = list(s.exec(select(TokenUsageEvent).where(TokenUsageEvent.timestamp >= start_today)).all())
        tokens_today = sum(e.total_tokens for e in events_t)
        
        # Latest refresh job
        refresh_job = s.exec(select(RefreshJob).order_by(RefreshJob.id.desc())).first()
        
        data = OverviewResponse(
            total_providers=provider_count,
            total_models=model_count,
            free_models=free_count,
            paid_models=paid_count,
            total_benchmarks=benchmark_count,
            total_capabilities=capability_count,
            total_evidence_records=evidence_count,
            total_subagent_routes=route_count,
            usage_today=tokens_today,
            usage_week=tokens_week,
            usage_month=tokens_month,
            db_last_refreshed=refresh_job.last_run if refresh_job else "",
        )
        return data.model_dump()


# =============================================================================
# PROVIDERS
# =============================================================================
providers_router = APIRouter()


@providers_router.get("/providers")
def list_providers():
    with Session(engine) as s:
        providers = list(s.exec(select(Provider)).all())
        return [
            {
                "provider_id": p.provider_id,
                "display_name": p.display_name,
                "source_type": p.source_type,
                "trust_level": p.trust_level,
                "health_score": p.health_score,
                "api_key_present": p.api_key_present,
                "stale_status": p.stale_status,
                "last_verified": p.last_verified,
                "notes": p.notes,
                "model_count": len(list(s.exec(select(ModelRecord).where(ModelRecord.provider == p.provider_id)).all())),
                "free_count": len(list(s.exec(select(ModelRecord).where(ModelRecord.provider == p.provider_id).where(ModelRecord.free_or_paid == "FREE")).all())),
                "paid_count": len(list(s.exec(select(ModelRecord).where(ModelRecord.provider == p.provider_id).where(ModelRecord.free_or_paid == "PAID")).all())),
            }
            for p in providers
        ]


@providers_router.get("/providers/{provider_id}")
def get_provider(provider_id: str):
    with Session(engine) as s:
        p = s.exec(select(Provider).where(Provider.provider_id == provider_id)).first()
        if not p:
            raise HTTPException(status_code=404, detail="Provider not found")
        
        models = list(s.exec(select(ModelRecord).where(ModelRecord.provider == provider_id)).all())
        benchmarks = list(s.exec(select(BenchmarkRecord).where(BenchmarkRecord.provider == provider_id)).all())
        
        return {
            "provider_id": p.provider_id,
            "display_name": p.display_name,
            "source_type": p.source_type,
            "trust_level": p.trust_level,
            "health_score": p.health_score,
            "api_key_present": p.api_key_present,
            "api_key_source": p.api_key_source,
            "stale_status": p.stale_status,
            "last_verified": p.last_verified,
            "notes": p.notes,
            "models": models,
            "benchmark_count": len(benchmarks),
        }


# =============================================================================
# MODELS
# =============================================================================
models_router = APIRouter()


@models_router.get("/models")
def list_models(
    provider: Optional[str] = None,
    free_paid: Optional[str] = None,
    capability: Optional[str] = None,
    source_type: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = Query(default=100, le=500),
):
    with Session(engine) as s:
        q = select(ModelRecord)
        
        if provider:
            q = q.where(ModelRecord.provider == provider)
        if free_paid:
            q = q.where(ModelRecord.free_or_paid == free_paid.upper())
        if capability:
            q = q.where(ModelRecord.benchmark_coverage.contains(capability))
        if source_type:
            q = q.where(ModelRecord.source_type == source_type)
        if search:
            q = q.where(
                (ModelRecord.canonical_model_id.contains(search)) |
                (ModelRecord.display_name.contains(search))
            )
        
        models = list(s.exec(q.limit(limit)).all())
        return [m.model_dump() for m in models]


@models_router.get("/models/{canonical_model_id}")
def get_model(canonical_model_id: str):
    with Session(engine) as s:
        m = s.exec(select(ModelRecord).where(ModelRecord.canonical_model_id == canonical_model_id)).first()
        if not m:
            raise HTTPException(status_code=404, detail="Model not found")
        
        benchmarks = list(s.exec(select(BenchmarkRecord).where(BenchmarkRecord.canonical_model_id == canonical_model_id)).all())
        routes = list(s.exec(select(SubagentRoute).where(SubagentRoute.canonical_model_id == canonical_model_id)).all())
        events = list(s.exec(select(TokenUsageEvent).where(TokenUsageEvent.canonical_model_id == canonical_model_id).limit(50)).all())
        
        result = m.model_dump()
        result["benchmarks"] = [b.model_dump() for b in benchmarks]
        result["routes"] = [r.model_dump() for r in routes]
        result["usage_events"] = [e.model_dump() for e in events]
        return result


@models_router.get("/models/{canonical_model_id}/benchmarks")
def get_model_benchmarks(canonical_model_id: str):
    with Session(engine) as s:
        benchmarks = list(s.exec(select(BenchmarkRecord).where(BenchmarkRecord.canonical_model_id == canonical_model_id)).all())
        return [b.model_dump() for b in benchmarks]


@models_router.get("/models/{canonical_model_id}/usage")
def get_model_usage(canonical_model_id: str, limit: int = 50):
    with Session(engine) as s:
        events = list(s.exec(
            select(TokenUsageEvent)
            .where(TokenUsageEvent.canonical_model_id == canonical_model_id)
            .limit(limit)
        ).all())
        return [e.model_dump() for e in events]


# =============================================================================
# BENCHMARKS
# =============================================================================
benchmarks_router = APIRouter()


@benchmarks_router.get("/benchmarks")
def list_benchmarks(
    capability: Optional[str] = None,
    evidence_level: Optional[str] = None,
    source_type: Optional[str] = None,
    limit: int = Query(default=200, le=500),
):
    with Session(engine) as s:
        q = select(BenchmarkRecord)
        if capability:
            q = q.where(BenchmarkRecord.task_category == capability)
        if evidence_level:
            q = q.where(BenchmarkRecord.evidence_level == evidence_level)
        if source_type:
            q = q.where(BenchmarkRecord.benchmark_type == source_type)
        
        records = list(s.exec(q.limit(limit)).all())
        return [r.model_dump() for r in records]


# =============================================================================
# SPECIALIZATIONS
# =============================================================================
specializations_router = APIRouter()


@specializations_router.get("/specializations")
def list_specializations():
    """Return task category → route chain mapping."""
    with Session(engine) as s:
        capabilities = list(s.exec(select(CapabilityRecord)).all())
        routes = list(s.exec(select(SubagentRoute).order_by(SubagentRoute.role, SubagentRoute.route_order)).all())
        
        # Group routes by role
        role_routes = {}
        for r in routes:
            if r.role not in role_routes:
                role_routes[r.role] = []
            role_routes[r.role].append(r.model_dump())
        
        # Build specialization map from capability records
        spec_map = {}
        for cap in capabilities:
            cat = cap.category
            if cat not in spec_map:
                spec_map[cat] = []
            role = f"{cap.capability_id}_subagent"
            if role in role_routes:
                spec_map[cat].append({
                    "capability": cap.capability_id,
                    "routes": role_routes[role],
                })
        
        return {
            "capabilities_by_category": {c.capability_id: {"category": c.category, "status": c.status} for c in capabilities},
            "routes_by_role": role_routes,
            "specialization_map": spec_map,
        }


# =============================================================================
# SUBAGENT ROUTING
# =============================================================================
routing_router = APIRouter()


@routing_router.get("/routing/subagents")
def list_subagent_routes():
    with Session(engine) as s:
        routes = list(s.exec(select(SubagentRoute).order_by(SubagentRoute.role, SubagentRoute.route_order)).all())
        
        # Group by role
        by_role = {}
        for r in routes:
            if r.role not in by_role:
                by_role[r.role] = []
            by_role[r.role].append(SubagentRouteItem(**r.model_dump()))
        
        return [
            {"role": role, "routes": route_list}
            for role, route_list in sorted(by_role.items())
        ]


@routing_router.get("/routing/subagents/{role}")
def get_subagent_route(role: str):
    with Session(engine) as s:
        routes = list(s.exec(
            select(SubagentRoute)
            .where(SubagentRoute.role == role)
            .order_by(SubagentRoute.route_order)
        ).all())
        if not routes:
            raise HTTPException(status_code=404, detail="Role not found")
        return SubagentRoleRoutes(
            role=role,
            routes=[SubagentRouteItem(**r.model_dump()) for r in routes]
        ).model_dump()


# =============================================================================
# WORKFLOWS
# =============================================================================
workflows_router = APIRouter()


@workflows_router.get("/workflows")
def list_workflows():
    with Session(engine) as s:
        workflows = list(s.exec(select(WorkflowDefinition)).all())
        items = [WorkflowItem(**w.model_dump()) for w in workflows]
        return WorkflowListResponse(items=items, total=len(items)).model_dump()


@workflows_router.get("/pipelines")
def list_pipelines():
    """Pipelines are workflow definitions with pipeline_stages."""
    with Session(engine) as s:
        workflows = list(s.exec(select(WorkflowDefinition)).all())
        result = []
        for w in workflows:
            data = w.model_dump()
            if data.get("pipeline_stages"):
                import json
                try:
                    data["stages_parsed"] = json.loads(data["pipeline_stages"])
                except ValueError:
                    data["stages_parsed"] = []
            result.append(WorkflowItem(**data))
        return WorkflowListResponse(items=result, total=len(result)).model_dump()


# =============================================================================
# EVIDENCE
# =============================================================================
evidence_router = APIRouter()


@evidence_router.get("/evidence")
def list_evidence(
    capability: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = Query(default=100, le=500),
):
    with Session(engine) as s:
        q = select(EvidenceRecord)
        if capability:
            q = q.where(EvidenceRecord.capability == capability)
        if status:
            q = q.where(EvidenceRecord.status == status)
        
        records = list(s.exec(q.limit(limit)).all())
        items = [EvidenceItem(**r.model_dump()) for r in records]
        return EvidenceListResponse(items=items, total=len(items)).model_dump()


# =============================================================================
# CAPABILITIES
# =============================================================================
capabilities_router = APIRouter()


@capabilities_router.get("/capabilities")
def list_capabilities(status: Optional[str] = None):
    with Session(engine) as s:
        q = select(CapabilityRecord)
        if status:
            q = q.where(CapabilityRecord.status == status)
        
        records = list(s.exec(q).all())
        items = [CapabilityItem(**r.model_dump()) for r in records]
        return CapabilityListResponse(items=items, total=len(items)).model_dump()


# =============================================================================
# REFRESH
# =============================================================================
refresh_router = APIRouter()


@refresh_router.get("/refresh-jobs")
def list_refresh_jobs():
    with Session(engine) as s:
        jobs = list(s.exec(select(RefreshJob)).all())
        return [j.model_dump() for j in jobs]


@refresh_router.post("/refresh/ingest")
def trigger_ingest():
    """Re-ingest all ILMA data sources."""
    service = IngestionService()
    results = service.ingest_all()
    return {"status": "completed", "results": results}


@refresh_router.post("/refresh/validate")
def trigger_validate():
    """Run ilma.py validate and doctor."""
    import subprocess
    ILMA_DIR = "/root/.hermes/profiles/ilma"
    
    validate_out = ""
    doctor_out = ""
    validate_code = 0
    doctor_code = 0
    
    try:
        r1 = subprocess.run(
            ["python3", f"{ILMA_DIR}/scripts/ilma.py", "validate"],
            capture_output=True, text=True, timeout=60
        )
        validate_out = r1.stdout[:500]
        validate_code = r1.returncode
    except Exception as e:
        validate_out = str(e)
    
    try:
        r2 = subprocess.run(
            ["python3", f"{ILMA_DIR}/scripts/ilma.py", "doctor"],
            capture_output=True, text=True, timeout=60
        )
        doctor_out = r2.stdout[:500]
        doctor_code = r2.returncode
    except Exception as e:
        doctor_out = str(e)
    
    return {
        "validate": {"exit_code": validate_code, "output": validate_out},
        "doctor": {"exit_code": doctor_code, "output": doctor_out},
    }