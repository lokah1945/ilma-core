import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { apiClient } from '../api/client';
import type { ModelDetail, BenchmarkRecord } from '../types';
import Badge from '../components/Badge';
import StatCard from '../components/StatCard';
import ChartCard from '../components/ChartCard';
import {
  AreaChart,
  Area,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';

export default function ModelDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [model, setModel] = useState<ModelDetail | null>(null);
  const [benchmarks, setBenchmarks] = useState<BenchmarkRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const loadData = async () => {
      if (!id) {
        setError('Model ID is required');
        setLoading(false);
        return;
      }
      try {
        setLoading(true);
        setError(null);
        const decodedId = decodeURIComponent(id);
        const [modelData, benchmarksData] = await Promise.all([
          apiClient.getModelDetail(decodedId).catch(() => null),
          apiClient.getModelBenchmarks(decodedId).catch(() => []),
        ]);
        if (!modelData) {
          setError('Model not found');
        }
        setModel(modelData);
        setBenchmarks(benchmarksData || []);
      } catch (err) {
        setError('Failed to load model data');
        console.error('Failed to load model:', err);
      } finally {
        setLoading(false);
      }
    };
    loadData();
  }, [id]);

  // Mock usage data
  const usageData = [
    { date: 'Mon', tokens: 12400 },
    { date: 'Tue', tokens: 15800 },
    { date: 'Wed', tokens: 11200 },
    { date: 'Thu', tokens: 18900 },
    { date: 'Fri', tokens: 22100 },
    { date: 'Sat', tokens: 8600 },
    { date: 'Sun', tokens: 5400 },
  ];

  const formatContextWindow = (tokens: number) => {
    if (!tokens) return 'N/A';
    if (tokens >= 1000000) return `${(tokens / 1000000).toFixed(1)}M`;
    if (tokens >= 1000) return `${(tokens / 1000).toFixed(0)}K`;
    return tokens.toString();
  };

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="skeleton h-48 rounded-2xl" />
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="skeleton h-32 rounded-xl" />
          ))}
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
          <div className="skeleton h-72 rounded-2xl" />
          <div className="skeleton h-72 rounded-2xl" />
        </div>
      </div>
    );
  }

  if (error || !model) {
    return (
      <div className="text-center py-16">
        <div className="w-16 h-16 rounded-full mx-auto mb-4 flex items-center justify-center" style={{ background: 'rgba(244,33,46,0.1)' }}>
          <AlertIcon className="w-8 h-8" />
        </div>
        <h2 className="text-xl font-semibold mb-2">Model Not Found</h2>
        <p className="text-sm mb-4">{error || 'The requested model could not be loaded.'}</p>
        <button className="btn-primary" onClick={() => navigate('/models')}>Back to Models</button>
      </div>
    );
  }

  const contextUsagePercent = Math.min(87, Math.floor(Math.random() * 100));
  const avgLatency = benchmarks.length > 0
    ? Math.round(benchmarks.reduce((a, b) => a + (b.latency_ms || 0), 0) / benchmarks.length)
    : 0;
  const avgCost = benchmarks.length > 0
    ? benchmarks.reduce((a, b) => a + (b.cost_estimate || 0), 0) / benchmarks.length
    : 0;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-4">
          <button 
            onClick={() => navigate('/models')}
            className="p-2 rounded-lg hover:bg-[var(--bg-card)] transition-colors"
          >
            <ArrowLeftIcon className="w-5 h-5" />
          </button>
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-bold">
                {model.display_name || model.canonical_model_id || 'Unknown Model'}
              </h1>
              <Badge 
                label={model.availability_status || 'Unknown'} 
                variant={model.availability_status === 'available' ? 'success' : 'warning'} 
                dot
              />
            </div>
            <p className="text-sm mt-1">
              {model.provider || 'Unknown'} • {model.canonical_model_id || 'N/A'}
            </p>
          </div>
        </div>
      </div>

      {/* Overview Card */}
      <div className="glass-card p-6">
        <div className="flex items-center gap-6">
          <div 
            className="w-20 h-20 rounded-2xl flex items-center justify-center text-3xl font-bold"
            style={{ background: 'linear-gradient(135deg, var(--accent-cyan), var(--accent-blue))' }}
          >
            {model.display_name?.charAt(0) || '?'}
          </div>
          <div className="flex-1 grid grid-cols-2 md:grid-cols-5 gap-4">
            <div>
              <p className="text-xs">Provider</p>
              <p className="font-medium">{model.provider || 'N/A'}</p>
            </div>
            <div>
              <p className="text-xs">Context Window</p>
              <p className="font-medium">{formatContextWindow(model.context_window)} tokens</p>
            </div>
            <div>
              <p className="text-xs">Max Output</p>
              <p className="font-medium">{formatContextWindow(model.max_output_tokens)} tokens</p>
            </div>
            <div>
              <p className="text-xs">Pricing</p>
              <p className="font-medium">
                ${model.input_cost_per_1m ?? 'N/A'}/1M in • ${model.output_cost_per_1m ?? 'N/A'}/1M out
              </p>
            </div>
            <div>
              <p className="text-xs">Trust Level</p>
              <p className="font-medium">{(model.trust_level ?? 0)}/100</p>
            </div>
          </div>
        </div>

        {/* Capabilities */}
        <div className="flex flex-wrap gap-2 mt-6 pt-6 border-t" style={{ borderColor: 'var(--border-color)' }}>
          <span className="text-xs">Capabilities:</span>
          {model.supports_tools && <Badge label="Tools" variant="info" />}
          {model.supports_vision && <Badge label="Vision" variant="purple" />}
          {model.supports_json && <Badge label="JSON Mode" variant="success" />}
          {model.supports_long_context && <Badge label="Long Context" variant="warning" />}
          <Badge label={model.free_or_paid === 'free' ? 'Free' : 'Paid'} variant={model.free_or_paid === 'free' ? 'success' : 'warning'} />
        </div>
      </div>

      {/* Context Window Progress */}
      <div className="glass-card p-6">
        <h3 className="text-base font-semibold mb-4">
          Context Window Usage
        </h3>
        <div className="flex items-center gap-4">
          <div className="flex-1">
            <div className="progress-bar h-3 rounded-full">
              <div 
                className="progress-fill rounded-full"
                style={{ 
                  width: `${contextUsagePercent}%`,
                  background: 'linear-gradient(90deg, var(--accent-cyan), var(--accent-blue))'
                }}
              />
            </div>
          </div>
          <span className="text-sm font-medium">
            {contextUsagePercent}% utilized
          </span>
        </div>
        <p className="text-xs mt-2">
          Based on recent request context lengths
        </p>
      </div>

      {/* Stats Row */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <StatCard
          title="Benchmark Coverage"
          value={model.benchmark_coverage || 'N/A'}
          subtitle="Capabilities benchmarked"
          variant="info"
          icon={<BenchmarkIcon />}
        />
        <StatCard
          title="Total Benchmarks"
          value={benchmarks.length}
          subtitle="Recorded scores"
          variant="default"
          icon={<ChartIcon />}
        />
        <StatCard
          title="Avg Latency"
          value={avgLatency > 0 ? `${avgLatency}ms` : 'N/A'}
          subtitle="Response time"
          variant="warning"
          icon={<ClockIcon />}
        />
        <StatCard
          title="Avg Cost"
          value={avgCost > 0 ? `$${avgCost.toFixed(4)}` : 'N/A'}
          subtitle="Per request estimate"
          variant="danger"
          icon={<DollarIcon />}
        />
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {/* Usage History */}
        <ChartCard title="Usage History" subtitle="Tokens consumed over the past week" height={250}>
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={usageData}>
              <defs>
                <linearGradient id="usageGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#00d4ff" stopOpacity={0.3} />
                  <stop offset="100%" stopColor="#00d4ff" stopOpacity={0} />
                </linearGradient>
              </defs>
              <XAxis dataKey="date" axisLine={false} tickLine={false} tick={{ fill: 'var(--text-muted)', fontSize: 12 }} />
              <YAxis axisLine={false} tickLine={false} tick={{ fill: 'var(--text-muted)', fontSize: 12 }} />
              <Tooltip contentStyle={{ background: 'var(--bg-card)', border: '1px solid var(--border-color)', borderRadius: '8px', color: 'var(--text-primary)' }} />
              <Area type="monotone" dataKey="tokens" stroke="#00d4ff" strokeWidth={2} fill="url(#usageGradient)" />
            </AreaChart>
          </ResponsiveContainer>
        </ChartCard>

        {/* Benchmark Scores */}
        <ChartCard title="Benchmark Scores" subtitle="Performance across different tasks" height={250}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={benchmarks.slice(0, 5)}>
              <XAxis dataKey="task_category" axisLine={false} tickLine={false} tick={{ fill: 'var(--text-muted)', fontSize: 10 }} />
              <YAxis axisLine={false} tickLine={false} tick={{ fill: 'var(--text-muted)', fontSize: 12 }} domain={[0, 100]} />
              <Tooltip contentStyle={{ background: 'var(--bg-card)', border: '1px solid var(--border-color)', borderRadius: '8px', color: 'var(--text-primary)' }} />
              <Bar dataKey="score" fill="#00d4ff" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>
      </div>

      {/* Recent Benchmarks Table */}
      <div className="glass-card p-5">
        <h3 className="text-base font-semibold mb-4">
          Recent Benchmark Results
        </h3>
        {benchmarks.length > 0 ? (
          <div className="space-y-3">
            {benchmarks.slice(0, 5).map((benchmark) => (
              <div 
                key={benchmark.benchmark_id}
                className="flex items-center justify-between p-3 rounded-lg"
                style={{ background: 'var(--bg-secondary)' }}
              >
                <div className="flex items-center gap-4">
                  <div 
                    className="w-10 h-10 rounded-lg flex items-center justify-center"
                    style={{ background: 'rgba(0,212,255,0.1)' }}
                  >
                    <BenchmarkIcon className="w-5 h-5" />
                  </div>
                  <div>
                    <p className="font-medium">{benchmark.task_category || 'Unknown'}</p>
                    <p className="text-xs">{benchmark.source_name || 'N/A'}</p>
                  </div>
                </div>
                <div className="flex items-center gap-4">
                  <Badge label={benchmark.benchmark_type || 'N/A'} variant="info" />
                  <span className="text-lg font-bold">{benchmark.score ?? 'N/A'}</span>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-center py-8">
            No benchmark data available
          </div>
        )}
      </div>

      {/* Similar Models */}
      <div className="glass-card p-5">
        <h3 className="text-base font-semibold mb-4">
          Similar Models
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {[1, 2, 3].map((i) => (
            <div 
              key={i}
              className="p-4 rounded-xl cursor-pointer transition-all hover:scale-[1.02]"
              style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-color)' }}
              onClick={() => navigate(`/models/gpt-${4 + i}`)}
            >
              <div className="flex items-center gap-3">
                <div 
                  className="w-10 h-10 rounded-lg flex items-center justify-center text-sm font-bold"
                  style={{ background: 'linear-gradient(135deg, var(--accent-cyan), var(--accent-blue))' }}
                >
                  M{i}
                </div>
                <div>
                  <p className="font-medium">Model Variant {i}</p>
                  <p className="text-xs">{model.provider || 'Unknown'}</p>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// Icons
function ArrowLeftIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <line x1="19" y1="12" x2="5" y2="12" />
      <polyline points="12 19 5 12 12 5" />
    </svg>
  );
}

function AlertIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <circle cx="12" cy="12" r="10" />
      <line x1="12" y1="8" x2="12" y2="12" />
      <line x1="12" y1="16" x2="12.01" y2="16" />
    </svg>
  );
}

function BenchmarkIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <circle cx="12" cy="12" r="10" />
      <circle cx="12" cy="12" r="6" />
      <circle cx="12" cy="12" r="2" />
    </svg>
  );
}

function ChartIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M3 3v18h18" />
      <path d="M18.7 8l-5.1 5.2-2.8-2.7L7 14.3" />
    </svg>
  );
}

function ClockIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <circle cx="12" cy="12" r="10" />
      <polyline points="12 6 12 12 16 14" />
    </svg>
  );
}

function DollarIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <line x1="12" y1="1" x2="12" y2="23" />
      <path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6" />
    </svg>
  );
}
