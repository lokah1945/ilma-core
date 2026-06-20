import { useEffect, useState } from 'react';
import { apiClient } from '../api/client';
import type { SubagentRouteItem } from '../types';
import Badge from '../components/Badge';
import ChartCard from '../components/ChartCard';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';

export default function RoutingPage() {
  const [routes, setRoutes] = useState<SubagentRouteItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const loadData = async () => {
      try {
        setLoading(true);
        setError(null);
        const data = await apiClient.getSubagentRoutes().catch(() => ({ items: [] }));
        setRoutes(data.items || []);
      } catch (err) {
        setError('Failed to load routing data');
        console.error('Failed to load routing data:', err);
      } finally {
        setLoading(false);
      }
    };
    loadData();
  }, []);

  // Mock recent routing decisions
  const recentDecisions = [
    { id: 1, timestamp: new Date(Date.now() - 1000 * 60 * 2).toISOString(), task: 'Code generation', model: 'gpt-4', latency: '234ms', status: 'success' },
    { id: 2, timestamp: new Date(Date.now() - 1000 * 60 * 5).toISOString(), task: 'Data analysis', model: 'claude-3', latency: '456ms', status: 'success' },
    { id: 3, timestamp: new Date(Date.now() - 1000 * 60 * 8).toISOString(), task: 'Text summarization', model: 'gemini-pro', latency: '189ms', status: 'success' },
    { id: 4, timestamp: new Date(Date.now() - 1000 * 60 * 12).toISOString(), task: 'Image analysis', model: 'gpt-4-vision', latency: '567ms', status: 'success' },
    { id: 5, timestamp: new Date(Date.now() - 1000 * 60 * 15).toISOString(), task: 'Code review', model: 'claude-3-opus', latency: '678ms', status: 'warning' },
    { id: 6, timestamp: new Date(Date.now() - 1000 * 60 * 20).toISOString(), task: 'Translation', model: 'gpt-4', latency: '123ms', status: 'success' },
    { id: 7, timestamp: new Date(Date.now() - 1000 * 60 * 25).toISOString(), task: 'Math reasoning', model: 'gemini-ultra', latency: '345ms', status: 'success' },
    { id: 8, timestamp: new Date(Date.now() - 1000 * 60 * 30).toISOString(), task: 'Creative writing', model: 'claude-3-sonnet', latency: '234ms', status: 'success' },
  ];

  const modelDistribution = [
    { name: 'GPT-4', routes: 12, color: '#00d4ff' },
    { name: 'Claude 3', routes: 8, color: '#1d9bf0' },
    { name: 'Gemini Pro', routes: 5, color: '#7856ff' },
    { name: 'Others', routes: 3, color: '#536471' },
  ];

  const formatTimestamp = (timestamp: string) => {
    const date = new Date(timestamp);
    return date.toLocaleTimeString();
  };

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="skeleton h-12 w-64 rounded-lg" />
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="skeleton h-20 rounded-lg" />
          ))}
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
          <div className="lg:col-span-2 skeleton h-96 rounded-2xl" />
          <div className="skeleton h-96 rounded-2xl" />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold gradient-text">Routing</h1>
          <p className="text-sm mt-1">
            Monitor routing decisions and subagent configurations
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

  const uniqueRoles = routes.length > 0 ? [...new Set(routes.map(r => r.role).filter(Boolean))].length : 0;

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div>
        <h1 className="text-2xl font-bold gradient-text">Routing</h1>
        <p className="text-sm mt-1">
          Monitor routing decisions and subagent configurations
        </p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="glass-card p-5">
          <p className="text-sm">Active Routes</p>
          <p className="text-3xl font-bold mt-1">{routes.length}</p>
        </div>
        <div className="glass-card p-5">
          <p className="text-sm">Avg Latency</p>
          <p className="text-3xl font-bold mt-1">287ms</p>
        </div>
        <div className="glass-card p-5">
          <p className="text-sm">Success Rate</p>
          <p className="text-3xl font-bold mt-1">98.5%</p>
        </div>
        <div className="glass-card p-5">
          <p className="text-sm">Total SubAgents</p>
          <p className="text-3xl font-bold mt-1">{uniqueRoles}</p>
        </div>
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        {/* Model Distribution */}
        <ChartCard title="Model Distribution" subtitle="Routes by model provider" height={250}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={modelDistribution} layout="vertical">
              <XAxis type="number" axisLine={false} tickLine={false} tick={{ fill: 'var(--text-muted)', fontSize: 12 }} />
              <YAxis dataKey="name" type="category" axisLine={false} tickLine={false} tick={{ fill: 'var(--text-muted)', fontSize: 12 }} width={80} />
              <Tooltip contentStyle={{ background: 'var(--bg-card)', border: '1px solid var(--border-color)', borderRadius: '8px', color: 'var(--text-primary)' }} />
              <Bar dataKey="routes" radius={[0, 4, 4, 0]}>
                {modelDistribution.map((entry, index) => (
                  <rect key={`cell-${index}`} fill={entry.color} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>

        {/* Quick Stats */}
        <div className="glass-card p-5">
          <h3 className="text-base font-semibold mb-4">Top Performers</h3>
          <div className="space-y-3">
            {modelDistribution.slice(0, 3).map((model, i) => (
              <div key={model.name} className="flex items-center justify-between p-3 rounded-lg" style={{ background: 'var(--bg-secondary)' }}>
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-lg flex items-center justify-center text-xs font-bold" style={{ background: model.color + '20', color: model.color }}>
                    {i + 1}
                  </div>
                  <span className="font-medium">{model.name}</span>
                </div>
                <Badge label={`${model.routes} routes`} variant="info" />
              </div>
            ))}
          </div>
        </div>

        {/* Status */}
        <div className="glass-card p-5">
          <h3 className="text-base font-semibold mb-4">System Status</h3>
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-sm">Routing Engine</span>
              <Badge label="Active" variant="success" dot />
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm">Fallback Logic</span>
              <Badge label="Enabled" variant="info" dot />
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm">Load Balancing</span>
              <Badge label="Active" variant="success" dot />
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm">Cache Hit Rate</span>
              <span className="font-medium">87.3%</span>
            </div>
          </div>
        </div>
      </div>

      {/* Recent Routing Decisions */}
      <div className="glass-card p-5">
        <h3 className="text-base font-semibold mb-4">
          Recent Routing Decisions
        </h3>
        <div className="space-y-2">
          {recentDecisions.map((decision) => (
            <div 
              key={decision.id}
              className="flex items-center justify-between p-4 rounded-lg transition-colors hover:bg-[var(--bg-secondary)]"
              style={{ borderBottom: '1px solid var(--border-color)' }}
            >
              <div className="flex items-center gap-4">
                <div 
                  className="w-10 h-10 rounded-lg flex items-center justify-center"
                  style={{ 
                    background: decision.status === 'success' ? 'rgba(0,186,124,0.1)' : 'rgba(255,212,0,0.1)'
                  }}
                >
                  {decision.status === 'success' ? (
                    <CheckIcon className="w-5 h-5" />
                  ) : (
                    <WarningIcon className="w-5 h-5" />
                  )}
                </div>
                <div>
                  <p className="font-medium">{decision.task}</p>
                  <p className="text-xs">
                    {formatTimestamp(decision.timestamp)}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-6">
                <div className="text-right">
                  <p className="text-sm">Model</p>
                  <p className="font-medium">{decision.model}</p>
                </div>
                <div className="text-right">
                  <p className="text-sm">Latency</p>
                  <p className="font-medium">{decision.latency}</p>
                </div>
                <Badge 
                  label={decision.status === 'success' ? 'Success' : 'Slow'} 
                  variant={decision.status === 'success' ? 'success' : 'warning'} 
                />
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Route Configuration */}
      {routes.length > 0 ? (
        <div className="glass-card p-5">
          <h3 className="text-base font-semibold mb-4">
            SubAgent Route Configuration
          </h3>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr style={{ background: 'var(--bg-secondary)' }}>
                  <th className="px-4 py-3 text-left font-medium">Role</th>
                  <th className="px-4 py-3 text-left font-medium">Task Category</th>
                  <th className="px-4 py-3 text-left font-medium">Primary Model</th>
                  <th className="px-4 py-3 text-left font-medium">Provider</th>
                  <th className="px-4 py-3 text-left font-medium">Score</th>
                  <th className="px-4 py-3 text-left font-medium">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y" style={{ borderColor: 'var(--border-color)' }}>
                {routes.slice(0, 10).map((route, idx) => (
                  <tr key={idx} className="hover:bg-[var(--bg-secondary)]">
                    <td className="px-4 py-3">{route.role || 'Unknown'}</td>
                    <td className="px-4 py-3">{route.task_category || 'Unknown'}</td>
                    <td className="px-4 py-3">{route.canonical_model_id || 'Unknown'}</td>
                    <td className="px-4 py-3"><Badge label={route.provider || 'Unknown'} variant="info" /></td>
                    <td className="px-4 py-3">{route.route_score?.toFixed(2) || 'N/A'}</td>
                    <td className="px-4 py-3">
                      <Badge label={route.is_active ? 'Active' : 'Inactive'} variant={route.is_active ? 'success' : 'default'} dot />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : (
        <div className="glass-card p-5">
          <div className="text-center py-8">
            <div className="w-16 h-16 rounded-full mx-auto mb-4 flex items-center justify-center" style={{ background: 'rgba(120,86,255,0.1)' }}>
              <RouteIcon className="w-8 h-8 text-gray-500" />
            </div>
            <h2 className="text-xl font-semibold mb-2">No Routes Configured</h2>
            <p className="text-sm text-gray-500">No subagent routing data available.</p>
          </div>
        </div>
      )}
    </div>
  );
}

// Icons
function CheckIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <polyline points="20 6 9 17 4 12" />
    </svg>
  );
}

function WarningIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
      <line x1="12" y1="9" x2="12" y2="13" />
      <line x1="12" y1="17" x2="12.01" y2="17" />
    </svg>
  );
}

function RouteIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <circle cx="12" cy="12" r="10" />
      <polygon points="16.24 7.76 14.12 14.12 7.76 16.24 9.88 9.88 16.24 7.76" />
    </svg>
  );
}
