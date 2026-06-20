// TypeScript types matching ILMA Dashboard API

export interface OverviewResponse {
  total_providers: number;
  total_models: number;
  free_models: number;
  paid_models: number;
  total_benchmarks: number;
  total_capabilities: number;
  total_evidence_records: number;
  total_subagent_routes: number;
  usage_today: number;
  usage_week: number;
  usage_month: number;
  db_last_refreshed: string;
}

export interface HealthResponse {
  status: string;
  timestamp: string;
  database: string;
  version: string;
}

// Provider types
export interface ProviderSummary {
  provider_id: string;
  display_name: string;
  source_type: string;
  trust_level: number;
  api_key_present: boolean;
  health_score: number;
  model_count: number;
}

export interface ModelSummary {
  canonical_model_id: string;
  provider: string;
  display_name: string;
  free_or_paid: string;
  availability_status: string;
  context_window: number;
  source_type: string;
  trust_level: number;
  supports_tools: boolean;
  supports_vision: boolean;
}

export interface ProviderDetail extends ProviderSummary {
  api_key_source: string;
  last_verified: string;
  stale_status: string;
  notes: string;
  models: ModelSummary[];
}

// Model types
export interface BenchmarkDetail {
  benchmark_id: string;
  canonical_model_id: string;
  provider: string;
  task_category: string;
  score: number;
  benchmark_type: string;
  evidence_level: string;
  source_name: string;
  source_url: string;
  latency_ms: number;
  cost_estimate: number;
  quality_notes: string;
  benchmarked_at: string;
  caveat: string;
}

export interface ModelDetail {
  canonical_model_id: string;
  provider: string;
  provider_model_id: string;
  display_name: string;
  aliases: string;
  free_or_paid: string;
  allowed_by_policy: boolean;
  availability_status: string;
  context_window: number;
  max_output_tokens: number;
  input_cost_per_1m: number;
  output_cost_per_1m: number;
  modality: string;
  supports_tools: boolean;
  supports_json: boolean;
  supports_vision: boolean;
  supports_long_context: boolean;
  source_type: string;
  trust_level: number;
  last_verified: string;
  benchmark_coverage: string;
  caveat: string;
  benchmarks: BenchmarkDetail[];
}

// Benchmark types
export interface BenchmarkRecord {
  benchmark_id: string;
  canonical_model_id: string;
  provider: string;
  task_category: string;
  score: number;
  benchmark_type: string;
  evidence_level: string;
  source_name: string;
  source_url: string;
  latency_ms: number;
  cost_estimate: number;
  quality_notes: string;
  benchmarked_at: string;
  caveat: string;
}

// Usage types
export interface UsageSummary {
  period: string;
  total_requests: number;
  total_tokens: number;
  total_cost: number;
  by_provider: Record<string, number>;
  by_model: Record<string, number>;
  by_subagent: Record<string, number>;
  by_workflow: Record<string, number>;
  by_category: Record<string, number>;
}

export interface DailyUsageItem {
  date: string;
  total_requests: number;
  total_tokens: number;
  total_cost: number;
}

export interface DailyUsageResponse {
  start: string;
  end: string;
  items: DailyUsageItem[];
}

// Capability types
export interface CapabilityItem {
  capability_id: string;
  capability_name: string;
  category: string;
  status: string;
  implementation_path: string;
  test_path: string;
  evidence_id: string;
  last_verified: string;
  caveat: string;
}

export interface CapabilityListResponse {
  items: CapabilityItem[];
  total: number;
}

// Evidence types
export interface EvidenceItem {
  evidence_id: string;
  claim: string;
  capability: string;
  test_performed: string;
  result: string;
  status: string;
  confidence: number;
  source_file: string;
  next_retest: string;
  timestamp: string;
}

export interface EvidenceListResponse {
  items: EvidenceItem[];
  total: number;
}

// Routing types
export interface SubagentRouteItem {
  role: string;
  task_category: string;
  route_order: number;
  provider: string;
  canonical_model_id: string;
  provider_model_id: string;
  free_or_paid: string;
  route_score: number;
  specialization_score: number;
  benchmark_score: number;
  provider_trust: number;
  fallback_reason: string;
  is_active: boolean;
}

export interface SubagentRoutesResponse {
  items: SubagentRouteItem[];
  total: number;
}

export interface SubagentRoleRoutes {
  role: string;
  routes: SubagentRouteItem[];
}

// Workflow types
export interface WorkflowItem {
  workflow_id: string;
  workflow_name: string;
  trigger: string;
  pipeline_stages: string;
  tools_used: string;
  subagent_roles: string;
  model_routes: string;
  evidence_outputs: string;
  status: string;
}

export interface WorkflowListResponse {
  items: WorkflowItem[];
  total: number;
}

// Specialization types
export interface SpecializationItem {
  canonical_model_id: string;
  provider: string;
  task_category: string;
  quality_score: number;
  coding_score: number;
  reasoning_score: number;
  tool_use_score: number;
  evidence_level: string;
}

// Refresh job types
export interface RefreshJobItem {
  job_id: string;
  job_name: string;
  source_type: string;
  last_run: string;
  next_run: string;
  status: string;
  records_updated: number;
  error: string;
}

// System health
export interface SystemHealthSnapshot {
  timestamp: string;
  total_tests: number;
  tests_passed: number;
  tests_failed: number;
  error_count: number;
  warning_count: number;
  validate_status: string;
  doctor_status: string;
  production_smoke: string;
  cron_status: string;
  db_freshness: string;
  stale_sources: string;
  broken_imports: string;
  ilma_version: string;
}

// Task types
export interface TaskRecord {
  task_id: string;
  task_type: string;
  status: string;
  created_at: string;
  completed_at?: string;
  result?: string;
  error?: string;
}

export interface TaskListResponse {
  items: TaskRecord[];
  total: number;
}