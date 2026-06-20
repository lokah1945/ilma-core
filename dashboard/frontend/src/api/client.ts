import axios from 'axios';
import type {
  OverviewResponse,
  HealthResponse,
  ProviderSummary,
  ProviderDetail,
  ModelSummary,
  ModelDetail,
  BenchmarkRecord,
  UsageSummary,
  DailyUsageResponse,
  CapabilityItem,
  CapabilityListResponse,
  EvidenceItem,
  EvidenceListResponse,
  SubagentRouteItem,
  SubagentRoutesResponse,
  SubagentRoleRoutes,
  WorkflowItem,
  WorkflowListResponse,
  SpecializationItem,
  RefreshJobItem,
  SystemHealthSnapshot
} from '../types';

const api = axios.create({
  baseURL: '/api',
  timeout: 10000,
});

export const apiClient = {
  // Health
  async getHealth(): Promise<HealthResponse> {
    const { data } = await api.get<HealthResponse>('/health');
    return data;
  },

  // Overview
  async getOverview(): Promise<OverviewResponse> {
    const { data } = await api.get<OverviewResponse>('/overview');
    return data;
  },

  // Providers
  async getProviders(): Promise<ProviderSummary[]> {
    const { data } = await api.get<ProviderSummary[]>('/providers');
    return data;
  },

  async getProviderDetail(providerId: string): Promise<ProviderDetail> {
    const { data } = await api.get<ProviderDetail>(`/providers/${providerId}`);
    return data;
  },

  // Models
  async getModels(params?: {
    provider?: string;
    free_paid?: string;
    capability?: string;
    source_type?: string;
  }): Promise<ModelSummary[]> {
    const { data } = await api.get<ModelSummary[]>('/models', { params });
    return data;
  },

  async getModelDetail(canonicalModelId: string): Promise<ModelDetail> {
    const { data } = await api.get<ModelDetail>(`/models/${encodeURIComponent(canonicalModelId)}`);
    return data;
  },

  async getModelBenchmarks(canonicalModelId: string): Promise<BenchmarkRecord[]> {
    const { data } = await api.get<BenchmarkRecord[]>(`/models/${encodeURIComponent(canonicalModelId)}/benchmarks`);
    return data;
  },

  async getModelUsage(canonicalModelId: string): Promise<any[]> {
    const { data } = await api.get<any[]>(`/models/${encodeURIComponent(canonicalModelId)}/usage`);
    return data;
  },

  // Benchmarks
  async getBenchmarks(params?: {
    capability?: string;
    evidence_level?: string;
    source_type?: string;
    provider?: string;
  }): Promise<BenchmarkRecord[]> {
    const { data } = await api.get<BenchmarkRecord[]>('/benchmarks', { params });
    return data;
  },

  // Specializations
  async getSpecializations(): Promise<SpecializationItem[]> {
    const { data } = await api.get<SpecializationItem[]>('/specializations');
    return data;
  },

  // Usage
  async getUsageSummary(params: {
    period: 'today' | 'week' | 'month';
    by?: 'provider' | 'model' | 'subagent' | 'workflow' | 'category';
  }): Promise<UsageSummary> {
    const { data } = await api.get<UsageSummary>('/usage/summary', { params });
    return data;
  },

  async getDailyUsage(params?: { start?: string; end?: string }): Promise<DailyUsageResponse> {
    const { data } = await api.get<DailyUsageResponse>('/usage/daily', { params });
    return data;
  },

  // Capabilities
  async getCapabilities(status?: string): Promise<CapabilityListResponse> {
    const { data } = await api.get<CapabilityListResponse>('/capabilities', {
      params: status ? { status } : undefined
    });
    return data;
  },

  // Evidence
  async getEvidence(params?: { capability?: string; status?: string }): Promise<EvidenceListResponse> {
    const { data } = await api.get<EvidenceListResponse>('/evidence', { params });
    return data;
  },

  // Routing
  async getSubagentRoutes(): Promise<SubagentRoutesResponse> {
    const { data } = await api.get<SubagentRoutesResponse>('/routing/subagents');
    return data;
  },

  async getSubagentRoleRoutes(role: string): Promise<SubagentRoleRoutes> {
    const { data } = await api.get<SubagentRoleRoutes>(`/routing/subagents/${encodeURIComponent(role)}`);
    return data;
  },

  // Workflows
  async getWorkflows(): Promise<WorkflowListResponse> {
    const { data } = await api.get<WorkflowListResponse>('/workflows');
    return data;
  },

  // Refresh jobs
  async getRefreshJobs(): Promise<RefreshJobItem[]> {
    const { data } = await api.get<RefreshJobItem[]>('/refresh-jobs');
    return data;
  },

  // System health
  async getSystemHealth(): Promise<SystemHealthSnapshot[]> {
    const { data } = await api.get<SystemHealthSnapshot[]>('/system-health');
    return data;
  }
};

export default apiClient;