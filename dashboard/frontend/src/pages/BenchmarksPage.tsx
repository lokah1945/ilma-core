import { useEffect, useState, useMemo } from 'react';
import { apiClient } from '../api/client';
import type { BenchmarkRecord } from '../types';
import Badge from '../components/Badge';
import ChartCard from '../components/ChartCard';
import DataTable from '../components/DataTable';
import {
  BarChart,
  Bar,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts';

export default function BenchmarksPage() {
  const [benchmarks, setBenchmarks] = useState<BenchmarkRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedCapability, setSelectedCapability] = useState<string>('');

  useEffect(() => {
    const loadData = async () => {
      try {
        setLoading(true);
        setError(null);
        const data = await apiClient.getBenchmarks().catch(() => []);
        setBenchmarks(data || []);
      } catch (err) {
        setError('Failed to load benchmarks');
        console.error('Failed to load benchmarks:', err);
      } finally {
        setLoading(false);
      }
    };
    loadData();
  }, []);

  const capabilities = [...new Set(benchmarks.map(b => b.task_category).filter(Boolean))];
  
  const filteredBenchmarks = selectedCapability
    ? benchmarks.filter(b => b.task_category === selectedCapability)
    : benchmarks;

  // Aggregate scores by model
  const modelScores = useMemo(() => {
    const scores: Record<string, { total: number; count: number; provider: string }> = {};
    benchmarks.forEach(b => {
      if (!b.canonical_model_id) return;
      if (!scores[b.canonical_model_id]) {
        scores[b.canonical_model_id] = { total: 0, count: 0, provider: b.provider || 'Unknown' };
      }
      scores[b.canonical_model_id].total += b.score || 0;
      scores[b.canonical_model_id].count += 1;
    });
    return Object.entries(scores)
      .map(([model, data]) => ({
        model: model.length > 20 ? model.substring(0, 20) + '...' : model,
        avgScore: Math.round(data.total / data.count),
        provider: data.provider,
      }))
      .sort((a, b) => b.avgScore - a.avgScore)
      .slice(0, 10);
  }, [benchmarks]);

  // Radar chart data
  const radarData = useMemo(() => {
    const categories = [...new Set(benchmarks.map(b => b.task_category).filter(Boolean))].slice(0, 6);
    return categories.map(cat => {
      const catBenchmarks = benchmarks.filter(b => b.task_category === cat);
      const avgScore = catBenchmarks.length > 0
        ? Math.round(catBenchmarks.reduce((sum, b) => sum + (b.score || 0), 0) / catBenchmarks.length)
        : 0;
      return { category: cat, score: avgScore, fullMark: 100 };
    });
  }, [benchmarks]);

  const columns = [
    {
      key: 'canonical_model_id',
      header: 'Model',
      sortable: true,
      render: (b: BenchmarkRecord) => (
        <div className="flex items-center gap-3">
          <div 
            className="w-8 h-8 rounded-lg flex items-center justify-center text-xs font-bold"
            style={{ background: 'linear-gradient(135deg, var(--accent-cyan), var(--accent-blue))' }}
          >
            {b.canonical_model_id?.charAt(0) || '?'}
          </div>
          <span style={{ color: 'var(--text-primary)' }}>{b.canonical_model_id || 'Unknown'}</span>
        </div>
      ),
    },
    {
      key: 'task_category',
      header: 'Task',
      sortable: true,
      render: (b: BenchmarkRecord) => (
        <Badge label={b.task_category || 'Unknown'} variant="info" />
      ),
    },
    {
      key: 'score',
      header: 'Score',
      sortable: true,
      render: (b: BenchmarkRecord) => (
        <div className="flex items-center gap-2">
          <div className="w-16 h-2 rounded-full" style={{ background: 'var(--bg-secondary)' }}>
            <div 
              className="h-full rounded-full"
              style={{ 
                width: `${b.score || 0}%`,
                background: (b.score || 0) >= 80 ? 'var(--accent-green)' : (b.score || 0) >= 60 ? 'var(--accent-yellow)' : 'var(--accent-red)'
              }}
            />
          </div>
          <span className="font-bold" style={{ color: 'var(--accent-cyan)' }}>{b.score ?? 0}</span>
        </div>
      ),
    },
    {
      key: 'latency_ms',
      header: 'Latency',
      sortable: true,
      render: (b: BenchmarkRecord) => (
        <span style={{ color: 'var(--text-secondary)' }}>{b.latency_ms ?? 0}ms</span>
      ),
    },
    {
      key: 'evidence_level',
      header: 'Evidence',
      sortable: true,
      render: (b: BenchmarkRecord) => (
        <Badge 
          label={b.evidence_level || 'N/A'} 
          variant={b.evidence_level === 'HIGH' ? 'success' : b.evidence_level === 'MEDIUM' ? 'warning' : 'info'} 
        />
      ),
    },
    {
      key: 'source_name',
      header: 'Source',
      sortable: true,
      render: (b: BenchmarkRecord) => (
        <span style={{ color: 'var(--text-muted)' }}>{b.source_name || 'N/A'}</span>
      ),
    },
  ];

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="skeleton h-12 w-64 rounded-lg" />
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="skeleton h-20 rounded-lg" />
          ))}
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
          <div className="skeleton h-80 rounded-2xl" />
          <div className="skeleton h-80 rounded-2xl" />
        </div>
        <div className="skeleton h-64 rounded-xl" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold gradient-text">Benchmarks</h1>
          <p className="text-sm mt-1" style={{ color: 'var(--text-muted)' }}>
            Performance metrics and benchmark results across models
          </p>
        </div>
        <div className="bg-red-900/20 border border-red-800 rounded-lg p-6 text-center">
          <p className="text-red-400">{error}</p>
          <button
            onClick={() => window.location.reload()}
            className="mt-3 px-4 py-2 bg-red-800 hover:bg-red-700 rounded text-sm"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  const avgScore = benchmarks.length > 0
    ? Math.round(benchmarks.reduce((a, b) => a + (b.score || 0), 0) / benchmarks.length)
    : 0;
  const avgLatency = benchmarks.length > 0
    ? Math.round(benchmarks.reduce((a, b) => a + (b.latency_ms || 0), 0) / benchmarks.length)
    : 0;

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div>
        <h1 className="text-2xl font-bold gradient-text">Benchmarks</h1>
        <p className="text-sm mt-1" style={{ color: 'var(--text-muted)' }}>
          Performance metrics and benchmark results across models
        </p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="glass-card p-5">
          <p className="text-sm" style={{ color: 'var(--text-muted)' }}>Total Benchmarks</p>
          <p className="text-3xl font-bold mt-1" style={{ color: 'var(--accent-cyan)' }}>{benchmarks.length}</p>
        </div>
        <div className="glass-card p-5">
          <p className="text-sm" style={{ color: 'var(--text-muted)' }}>Avg Score</p>
          <p className="text-3xl font-bold mt-1" style={{ color: 'var(--accent-green)' }}>{avgScore}</p>
        </div>
        <div className="glass-card p-5">
          <p className="text-sm" style={{ color: 'var(--text-muted)' }}>Models Tested</p>
          <p className="text-3xl font-bold mt-1" style={{ color: 'var(--accent-blue)' }}>{modelScores.length}</p>
        </div>
        <div className="glass-card p-5">
          <p className="text-sm" style={{ color: 'var(--text-muted)' }}>Avg Latency</p>
          <p className="text-3xl font-bold mt-1" style={{ color: 'var(--accent-yellow)' }}>{avgLatency}ms</p>
        </div>
      </div>

      {/* Charts */}
      {benchmarks.length > 0 && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
          {/* Model Comparison */}
          <ChartCard title="Top Models by Score" subtitle="Average benchmark scores" height={300}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={modelScores} layout="vertical">
                <XAxis type="number" domain={[0, 100]} axisLine={false} tickLine={false} tick={{ fill: 'var(--text-muted)', fontSize: 12 }} />
                <YAxis dataKey="model" type="category" axisLine={false} tickLine={false} tick={{ fill: 'var(--text-muted)', fontSize: 11 }} width={120} />
                <Tooltip contentStyle={{ background: 'var(--bg-card)', border: '1px solid var(--border-color)', borderRadius: '8px', color: 'var(--text-primary)' }} />
                <Bar dataKey="avgScore" fill="var(--accent-cyan)" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </ChartCard>

          {/* Radar Chart */}
          <ChartCard title="Capability Radar" subtitle="Average scores by task category" height={300}>
            <ResponsiveContainer width="100%" height="100%">
              <RadarChart data={radarData}>
                <PolarGrid stroke="var(--border-color)" />
                <PolarAngleAxis dataKey="category" tick={{ fill: 'var(--text-muted)', fontSize: 11 }} />
                <PolarRadiusAxis angle={90} domain={[0, 100]} tick={{ fill: 'var(--text-muted)', fontSize: 10 }} />
                <Radar name="Score" dataKey="score" stroke="var(--accent-cyan)" fill="var(--accent-cyan)" fillOpacity={0.3} />
                <Tooltip contentStyle={{ background: 'var(--bg-card)', border: '1px solid var(--border-color)', borderRadius: '8px', color: 'var(--text-primary)' }} />
              </RadarChart>
            </ResponsiveContainer>
          </ChartCard>
        </div>
      )}

      {/* Filter */}
      <div className="flex items-center gap-4">
        <select
          value={selectedCapability}
          onChange={(e) => setSelectedCapability(e.target.value)}
          className="input-field w-48"
        >
          <option value="">All Capabilities</option>
          {capabilities.map(c => (
            <option key={c} value={c}>{c}</option>
          ))}
        </select>
        
        {selectedCapability && (
          <button
            onClick={() => setSelectedCapability('')}
            className="text-sm hover:underline"
            style={{ color: 'var(--accent-cyan)' }}
          >
            Clear filter
          </button>
        )}
      </div>

      {/* Table */}
      {filteredBenchmarks.length > 0 ? (
        <DataTable
          columns={columns}
          data={filteredBenchmarks}
          keyExtractor={(b) => b.benchmark_id || `${b.canonical_model_id}-${b.task_category}`}
          loading={loading}
          emptyMessage="No benchmarks found"
          pageSize={20}
        />
      ) : (
        <div className="text-center py-16">
          <div className="w-16 h-16 rounded-full mx-auto mb-4 flex items-center justify-center" style={{ background: 'rgba(0,212,255,0.1)' }}>
            <BenchmarkIcon className="w-8 h-8 text-gray-500" />
          </div>
          <h2 className="text-xl font-semibold mb-2">No Benchmarks Found</h2>
          <p className="text-sm text-gray-500">No benchmark data available.</p>
        </div>
      )}
    </div>
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

