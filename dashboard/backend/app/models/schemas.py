"""
app/models/schemas.py — Pydantic v2 Request/Response Schemas
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


# =============================================================================
# OVERVIEW SCHEMAS
# =============================================================================
class OverviewResponse(BaseModel):
    """Dashboard overview totals"""
    total_providers: int = 0
    total_models: int = 0
    free_models: int = 0
    paid_models: int = 0
    total_benchmarks: int = 0
    total_capabilities: int = 0
    total_evidence_records: int = 0
    total_subagent_routes: int = 0
    usage_today: int = 0
    usage_week: int = 0
    usage_month: int = 0
    db_last_refreshed: str = ""


# =============================================================================
# PROVIDER SCHEMAS
# =============================================================================
class ProviderSummary(BaseModel):
    """Provider list item"""
    provider_id: str
    display_name: str
    source_type: str
    trust_level: int
    api_key_present: bool
    health_score: int
    model_count: int = 0


class ProviderDetail(BaseModel):
    """Provider detail with models"""
    provider_id: str
    display_name: str
    source_type: str
    trust_level: int
    api_key_present: bool
    api_key_source: str
    health_score: int
    last_verified: str
    stale_status: str
    notes: str
    models: List["ModelSummary"] = []


# =============================================================================
# MODEL SCHEMAS
# =============================================================================
class ModelSummary(BaseModel):
    """Model list item"""
    canonical_model_id: str
    provider: str
    display_name: str
    free_or_paid: str
    availability_status: str
    context_window: int
    source_type: str
    trust_level: int
    supports_tools: bool
    supports_vision: bool


class ModelDetail(BaseModel):
    """Full model detail"""
    canonical_model_id: str
    provider: str
    provider_model_id: str
    display_name: str
    aliases: str
    free_or_paid: str
    allowed_by_policy: bool
    availability_status: str
    context_window: int
    max_output_tokens: int
    input_cost_per_1m: float
    output_cost_per_1m: float
    modality: str
    supports_tools: bool
    supports_json: bool
    supports_vision: bool
    supports_long_context: bool
    source_type: str
    trust_level: int
    last_verified: str
    benchmark_coverage: str
    caveat: str
    benchmarks: List["BenchmarkDetail"] = []


# =============================================================================
# BENCHMARK SCHEMAS
# =============================================================================
class BenchmarkDetail(BaseModel):
    """Benchmark record detail"""
    benchmark_id: str
    canonical_model_id: str
    provider: str
    task_category: str
    score: float
    benchmark_type: str
    evidence_level: str
    source_name: str
    source_url: str
    latency_ms: float
    cost_estimate: float
    quality_notes: str
    benchmarked_at: str
    caveat: str


# =============================================================================
# USAGE SCHEMAS
# =============================================================================
class UsageSummary(BaseModel):
    """Usage summary response"""
    period: str
    total_requests: int = 0
    total_tokens: int = 0
    total_cost: float = 0.0
    by_provider: Dict[str, int] = {}
    by_model: Dict[str, int] = {}
    by_subagent: Dict[str, int] = {}
    by_workflow: Dict[str, int] = {}
    by_category: Dict[str, int] = {}


class DailyUsageItem(BaseModel):
    """Daily usage aggregation item"""
    date: str
    total_requests: int
    total_tokens: int
    total_cost: float


class DailyUsageResponse(BaseModel):
    """Daily usage response"""
    start: str
    end: str
    items: List[DailyUsageItem] = []


# =============================================================================
# CAPABILITY SCHEMAS
# =============================================================================
class CapabilityItem(BaseModel):
    """Capability registry item"""
    capability_id: str
    capability_name: str
    category: str
    status: str
    implementation_path: str
    test_path: str
    evidence_id: str
    last_verified: str
    caveat: str


class CapabilityListResponse(BaseModel):
    """List of capabilities"""
    items: List[CapabilityItem] = []
    total: int = 0


# =============================================================================
# EVIDENCE SCHEMAS
# =============================================================================
class EvidenceItem(BaseModel):
    """Evidence record"""
    evidence_id: str
    claim: str
    capability: str
    test_performed: str
    result: str
    status: str
    confidence: float
    source_file: str
    next_retest: str
    timestamp: str


class EvidenceListResponse(BaseModel):
    """List of evidence records"""
    items: List[EvidenceItem] = []
    total: int = 0


# =============================================================================
# ROUTING SCHEMAS
# =============================================================================
class SubagentRouteItem(BaseModel):
    """Subagent model route"""
    role: str
    task_category: str
    route_order: int
    provider: str
    canonical_model_id: str
    provider_model_id: str
    free_or_paid: str
    route_score: float
    specialization_score: float
    benchmark_score: float
    provider_trust: int
    fallback_reason: str
    is_active: bool


class SubagentRoutesResponse(BaseModel):
    """All subagent routes"""
    items: List[SubagentRouteItem] = []
    total: int = 0


class SubagentRoleRoutes(BaseModel):
    """Routes for a specific role"""
    role: str
    routes: List[SubagentRouteItem] = []


# =============================================================================
# WORKFLOW SCHEMAS
# =============================================================================
class WorkflowItem(BaseModel):
    """Workflow definition"""
    workflow_id: str
    workflow_name: str
    trigger: str
    pipeline_stages: str
    tools_used: str
    subagent_roles: str
    model_routes: str
    evidence_outputs: str
    status: str


class WorkflowListResponse(BaseModel):
    """List of workflows"""
    items: List[WorkflowItem] = []
    total: int = 0


# =============================================================================
# REFRESH JOB SCHEMAS
# =============================================================================
class RefreshJobItem(BaseModel):
    """Refresh job status"""
    job_id: str
    job_name: str
    source_type: str
    last_run: str
    next_run: str
    status: str
    records_updated: int
    error: str


# =============================================================================
# SPECIALIZATION SCHEMAS
# =============================================================================
class SpecializationItem(BaseModel):
    """Model specialization"""
    canonical_model_id: str
    provider: str
    task_category: str
    quality_score: float
    coding_score: float
    reasoning_score: float
    tool_use_score: float
    evidence_level: str


# =============================================================================
# HEALTH SCHEMAS
# =============================================================================
class HealthResponse(BaseModel):
    """API health check response"""
    status: str = "ok"
    timestamp: str = ""
    database: str = "connected"
    version: str = "1.0.0"


# Forward references
ProviderDetail.model_rebuild()
ModelDetail.model_rebuild()
