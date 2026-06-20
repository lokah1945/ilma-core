"""SQLModel table definitions for ILMA Dashboard."""
from sqlmodel import Field, SQLModel, Relationship
from typing import Optional, List


# =============================================================================
# PROVIDER
# =============================================================================
class Provider(SQLModel, table=True):
    __tablename__ = "providers"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    provider_id: str = Field(index=True, unique=True)  # nvidia, openai, qwen, etc.
    display_name: str
    source_type: str  # BRIDGE, NATIVE, OPENROUTER, ARTIFICIAL_ANALYSIS
    trust_level: int = Field(default=5)  # 1-10
    api_key_present: bool = Field(default=False)
    api_key_source: str = Field(default="")
    health_score: int = Field(default=50)  # 0-100
    last_verified: str = Field(default="")
    stale_status: str = Field(default="ACTIVE")  # ACTIVE, STALE, UNKNOWN
    notes: str = Field(default="")


# =============================================================================
# MODEL
# =============================================================================
class ModelRecord(SQLModel, table=True):
    __tablename__ = "model_ids"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    canonical_model_id: str = Field(index=True, unique=True)
    provider: str = Field(index=True)
    provider_model_id: str = Field(default="")
    display_name: str = Field(default="")
    aliases: str = Field(default="")  # comma-separated
    free_or_paid: str = Field(default="FREE")  # FREE, PAID
    allowed_by_policy: bool = Field(default=True)
    availability_status: str = Field(default="ACTIVE")  # ACTIVE, DEPRECATED, STALE, UNKNOWN
    context_window: int = Field(default=0)
    max_output_tokens: int = Field(default=0)
    input_cost_per_1m: float = Field(default=0.0)
    output_cost_per_1m: float = Field(default=0.0)
    modality: str = Field(default="text")  # text, image, audio, video
    supports_tools: bool = Field(default=False)
    supports_json: bool = Field(default=False)
    supports_vision: bool = Field(default=False)
    supports_long_context: bool = Field(default=False)
    source_type: str = Field(default="UNVERIFIED")
    trust_level: int = Field(default=5)
    last_verified: str = Field(default="")
    benchmark_coverage: str = Field(default="")
    caveat: str = Field(default="")
    
    # Benchmark-derived scores (from model_specialization_database.json)
    quality_score: float = Field(default=0.0)
    coding_score: float = Field(default=0.0)
    reasoning_score: float = Field(default=0.0)
    tool_use_score: float = Field(default=0.0)
    specialization: str = Field(default="")


# =============================================================================
# BENCHMARK
# =============================================================================
class BenchmarkRecord(SQLModel, table=True):
    __tablename__ = "benchmark_records"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    benchmark_id: str = Field(index=True, unique=True)
    canonical_model_id: str = Field(index=True)
    provider: str = Field(index=True)
    provider_model_id: str = Field(default="")
    task_category: str = Field(index=True)
    score: float = Field(default=0.0)
    benchmark_type: str = Field(default="UNVERIFIED")  # live, passive, provider, trusted, doc, dry_run, heuristic, inferred, unverified
    evidence_level: str = Field(default="UNVERIFIED")
    source_name: str = Field(default="")
    source_url: str = Field(default="")
    latency_ms: float = Field(default=0.0)
    cost_estimate: float = Field(default=0.0)
    quality_notes: str = Field(default="")
    benchmarked_at: str = Field(default="")
    caveat: str = Field(default="")


# =============================================================================
# TOKEN USAGE
# =============================================================================
class TokenUsageEvent(SQLModel, table=True):
    __tablename__ = "token_usage_events"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    timestamp: str = Field(index=True)
    provider: str = Field(index=True)
    model_id: str = Field(index=True)
    canonical_model_id: str = Field(default="")
    subagent_role: str = Field(default="")
    task_category: str = Field(default="")
    input_tokens: int = Field(default=0)
    output_tokens: int = Field(default=0)
    total_tokens: int = Field(default=0)
    estimated_cost: float = Field(default=0.0)
    free_or_paid: str = Field(default="FREE")
    request_status: str = Field(default="SUCCESS")  # SUCCESS, FAIL, PARTIAL
    workflow_id: str = Field(default="")
    route_trace_id: str = Field(default="")
    token_count_source: str = Field(default="ESTIMATED")  # EXACT, PROVIDER_REPORTED, ESTIMATED, UNKNOWN


# =============================================================================
# TOKEN USAGE AGGREGATES (daily/weekly/monthly)
# =============================================================================
class TokenUsageDaily(SQLModel, table=True):
    __tablename__ = "token_usage_daily"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    date: str = Field(index=True)  # YYYY-MM-DD
    provider: str = Field(index=True)
    model_id: str = Field(index=True)
    total_tokens: int = Field(default=0)
    total_cost: float = Field(default=0.0)
    success_count: int = Field(default=0)
    fail_count: int = Field(default=0)
    token_count_source: str = Field(default="ESTIMATED")


# =============================================================================
# CAPABILITY REGISTRY
# =============================================================================
class CapabilityRecord(SQLModel, table=True):
    __tablename__ = "capability_registry_records"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    capability_id: str = Field(index=True, unique=True)
    capability_name: str = Field(default="")
    category: str = Field(index=True)  # COGNITIVE, EXECUTIVE, CREATIVE, ANALYTICAL, OPERATIONAL
    status: str = Field(default="UNVERIFIED")  # VERIFIED, STRONGLY_SUPPORTED, PARTIAL, UNVERIFIED, BLOCKED, DEPRECATED
    implementation_path: str = Field(default="")
    test_path: str = Field(default="")
    evidence_id: str = Field(default="")
    last_verified: str = Field(default="")
    caveat: str = Field(default="")


# =============================================================================
# EVIDENCE
# =============================================================================
class EvidenceRecord(SQLModel, table=True):
    __tablename__ = "evidence_records"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    evidence_id: str = Field(index=True, unique=True)
    claim: str = Field(default="")
    capability: str = Field(index=True, default="")
    test_performed: str = Field(default="")
    result: str = Field(default="")
    status: str = Field(default="UNVERIFIED")  # VERIFIED, FAILED, PARTIAL, UNVERIFIED
    confidence: float = Field(default=0.0)
    source_file: str = Field(default="")
    next_retest: str = Field(default="")
    timestamp: str = Field(default="")


# =============================================================================
# SUBAGENT MODEL ROUTES
# =============================================================================
class SubagentRoute(SQLModel, table=True):
    __tablename__ = "subagent_model_routes"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    role: str = Field(index=True)
    task_category: str = Field(index=True)
    route_order: int = Field(default=1)  # 1=primary, 2+=fallback
    provider: str = Field(default="")
    canonical_model_id: str = Field(index=True)
    provider_model_id: str = Field(default="")
    free_or_paid: str = Field(default="FREE")
    route_score: float = Field(default=0.0)
    specialization_score: float = Field(default=0.0)
    benchmark_score: float = Field(default=0.0)
    provider_trust: int = Field(default=5)
    fallback_reason: str = Field(default="")
    blocked_paid_candidates: str = Field(default="")
    caveat: str = Field(default="")
    is_active: bool = Field(default=True)


# =============================================================================
# WORKFLOWS
# =============================================================================
class WorkflowDefinition(SQLModel, table=True):
    __tablename__ = "workflow_definitions"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    workflow_id: str = Field(index=True, unique=True)
    workflow_name: str = Field(default="")
    trigger: str = Field(default="")
    pipeline_stages: str = Field(default="")  # JSON array
    tools_used: str = Field(default="")  # JSON array
    subagent_roles: str = Field(default="")  # comma-separated
    model_routes: str = Field(default="")
    evidence_outputs: str = Field(default="")
    status: str = Field(default="ACTIVE")


class WorkflowRun(SQLModel, table=True):
    __tablename__ = "workflow_runs"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    workflow_id: str = Field(index=True)
    started_at: str = Field(default="")
    completed_at: str = Field(default="")
    status: str = Field(default="")
    duration_ms: float = Field(default=0.0)
    artifacts: str = Field(default="")


# =============================================================================
# REFRESH JOBS
# =============================================================================
class RefreshJob(SQLModel, table=True):
    __tablename__ = "refresh_jobs"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    job_id: str = Field(index=True, unique=True)
    job_name: str = Field(default="")
    source_type: str = Field(default="")
    last_run: str = Field(default="")
    next_run: str = Field(default="")
    status: str = Field(default="IDLE")  # IDLE, RUNNING, SUCCESS, FAILED
    records_updated: int = Field(default=0)
    error: str = Field(default="")


# =============================================================================
# TASK EXECUTION RECORDS
# =============================================================================
class TaskRecord(SQLModel, table=True):
    __tablename__ = "task_records"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    task_id: str = Field(index=True)
    task_name: str = Field(default="")
    subagent_role: str = Field(default="")
    task_category: str = Field(default="")
    canonical_model_id: str = Field(default="")
    provider: str = Field(default="")
    status: str = Field(default="")  # RUNNING, SUCCESS, FAILED
    started_at: str = Field(default="")
    completed_at: str = Field(default="")
    duration_ms: float = Field(default=0.0)
    error: str = Field(default="")


# =============================================================================
# SYSTEM HEALTH
# =============================================================================
class SystemHealthSnapshot(SQLModel, table=True):
    __tablename__ = "system_health_snapshots"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    timestamp: str = Field(index=True)
    total_tests: int = Field(default=0)
    tests_passed: int = Field(default=0)
    tests_failed: int = Field(default=0)
    validate_status: str = Field(default="")
    doctor_status: str = Field(default="")
    production_smoke: str = Field(default="")
    cron_status: str = Field(default="")
    db_freshness: str = Field(default="")
    stale_sources: str = Field(default="")
    broken_imports: str = Field(default="")
    error_count: int = Field(default=0)
    warning_count: int = Field(default=0)
    ilma_version: str = Field(default="3.24")