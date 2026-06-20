import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiClient } from '../api/client';
import type { OverviewResponse, HealthResponse } from '../types';
import StatCard from '../components/StatCard';
import ChartCard from '../components/ChartCard';
import ActivityFeed from '../components/ActivityFeed';
import Badge from '../components/Badge';
import {
  AreaChart,
  Area,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';

export default function OverviewPage() {
  const navigate = useNavigate();
  const [overview, setOverview] = useState<OverviewResponse | null>(null);
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const loadData = async () => {
      try {
        const [healthData, overviewData] = await Promise.all([
          apiClient.getHealth().catch(() => null),
          apiClient.getOverview().catch(() => null),
        ]);
        setHealth(healthData);
        setOverview(overviewData);
      } catch (err) {
        setError('Failed to load dashboard data');
      } finally {
        setLoading(false);
      }
    };
    loadData();
  }, []);

  // Generate mock data for demo
  const tasksData = [
    { day: 'Mon', tasks: 245 },
    { day: 'Tue', tasks: 312 },
    { day: 'Wed', tasks: 278 },
    { day: 'Thu', tasks: 356 },
    { day: 'Fri', tasks: 298 },
    { day: 'Sat', tasks: 187 },
    { day: 'Sun', tasks: 156 },
  ];

  const modelUsageData = [
    { name: 'GPT-4', value: 35, color: '#00d4ff' },
    { name: 'Claude', value: 28, color: '#1d9bf0' },
    { name: 'Gemini', value: 20, color: '#7856ff' },
    { name: 'Others', value: 17, color: '#536471' },
  ];

  const recentActivity = [
    { id: '1', timestamp: new Date(Date.now() - 1000 * 60 * 5).toISOString(), description: 'Model GPT-4o processed 1,234 tokens', status: 'success' as const },
    { id: '2', timestamp: new Date(Date.now() - 1000 * 60 * 15).toISOString(), description: 'Benchmark updated for claude-3-opus', status: 'info' as const },
    { id: '3', timestamp: new Date(Date.now() - 1000 * 60 * 30).toISOString(), description: 'Routing decision: researcher → gpt-4', status: 'success' as const },
    { id: '4', timestamp: new Date(Date.now() - 1000 * 60 * 60).toISOString(), description: 'Evidence verified for capability reasoning', status: 'success' as const },
    { id: '5', timestamp: new Date(Date.now() - 1000 * 60 * 90).toISOString(), description: 'Pipeline execution completed', status: 'warning' as const },
  ];

  const getHealthVariant = () => {
    if (!health) return 'warning';
    return health.status === 'ok' ? 'success' : 'danger';
  };

  const getHealthLabel = () => {
    if (!health) return 'Unknown';
    return health.status === 'ok' ? 'Healthy' : 'Issues Detected';
  };

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="skeleton h-32 rounded-2xl" />
          ))}
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
          <div className="skeleton h-80 rounded-2xl" />
          <div className="skeleton h-80 rounded-2xl" />
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold gradient-text">Dashboard Overview</h1>
          <p className="text-sm mt-1">
            Welcome back! Here's what's happening with ILMA.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button className="btn-secondary" onClick={() => navigate('/health')}>
            <span className="flex items-center gap-2">
              <RefreshIcon className="w-4 h-4" />
              Refresh
            </span>
          </button>
          <button className="btn-primary" onClick={() => navigate('/models')}>
            <span className="flex items-center gap-2">
              <PlayIcon className="w-4 h-4" />
              Run Task
            </span>
          </button>
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5">
        <div className="animate-fade-in stagger-1">
          <StatCard
            title="Total Models"
            value={overview?.total_models || 0}
            subtitle="Registered in the system"
            variant="info"
            icon={<ModelIcon />}
          />
        </div>
        <div className="animate-fade-in stagger-2">
          <StatCard
            title="Active Providers"
            value={overview?.total_providers || 0}
            subtitle="Configured providers"
            variant="success"
            icon={<CloudIcon />}
          />
        </div>
        <div className="animate-fade-in stagger-3">
          <StatCard
            title="Tasks Today"
            value="847"
            subtitle="+12% from yesterday"
            variant="default"
            trend="up"
            trendValue="12%"
            icon={<TaskIcon />}
          />
        </div>
        <div className="animate-fade-in stagger-4">
          <StatCard
            title="Success Rate"
            value="98.5%"
            subtitle="Last 24 hours"
            variant="success"
            icon={<CheckIcon />}
          />
        </div>
      </div>

      {/* System Health Banner */}
      <div 
        className="rounded-2xl p-5 border flex items-center justify-between"
        style={{ 
          background: getHealthVariant() === 'success' 
            ? 'linear-gradient(135deg, rgba(0,186,124,0.1), rgba(0,212,255,0.05))' 
            : 'linear-gradient(135deg, rgba(244,33,46,0.1), rgba(255,212,0,0.05))',
          borderColor: getHealthVariant() === 'success' ? 'rgba(0,186,124,0.3)' : 'rgba(244,33,46,0.3)'
        }}
      >
        <div className="flex items-center gap-4">
          <div 
            className={`w-12 h-12 rounded-xl flex items-center justify-center ${
              getHealthVariant() === 'success' ? 'animate-pulse-glow' : ''
            }`}
            style={{ 
              background: getHealthVariant() === 'success' ? 'rgba(0,186,124,0.2)' : 'rgba(244,33,46,0.2)',
            }}
          >
            <HeartIcon className="w-6 h-6" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-lg font-semibold"
              >
                {getHealthLabel()}
              </span>
              <Badge label={health?.status || 'unknown'} variant={getHealthVariant()} />
            </div>
            <p className="text-sm mt-0.5">
              Backend API • Database {health?.database || 'unknown'} • Version {health?.version || 'N/A'}
            </p>
          </div>
        </div>
        <button 
          className="btn-secondary"
          onClick={() => navigate('/health')}
        >
          View Details
        </button>
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        {/* Tasks Over Time */}
        <div className="lg:col-span-2 animate-fade-in" style={{ animationDelay: '0.2s' }}>
          <ChartCard
            title="Tasks Over Time"
            subtitle="Last 7 days task volume"
            action={
              <select 
                className="input-field w-auto text-sm py-1"
                style={{ paddingRight: '2rem' }}
              >
                <option>Last 7 days</option>
                <option>Last 30 days</option>
              </select>
            }
            height={260}
          >
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={tasksData}>
                <defs>
                  <linearGradient id="taskGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#00d4ff" stopOpacity={0.3} />
                    <stop offset="100%" stopColor="#00d4ff" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <XAxis 
                  dataKey="day" 
                  axisLine={false} 
                  tickLine={false}
                  tick={{ fill: 'var(--text-muted)', fontSize: 12 }}
                />
                <YAxis 
                  axisLine={false} 
                  tickLine={false}
                  tick={{ fill: 'var(--text-muted)', fontSize: 12 }}
                />
                <Tooltip 
                  contentStyle={{
                    background: 'var(--bg-card)',
                    border: '1px solid var(--border-color)',
                    borderRadius: '8px',
                    color: 'var(--text-primary)'
                  }}
                />
                <Area 
                  type="monotone" 
                  dataKey="tasks" 
                  stroke="#00d4ff" 
                  strokeWidth={2}
                  fill="url(#taskGradient)" 
                />
              </AreaChart>
            </ResponsiveContainer>
          </ChartCard>
        </div>

        {/* Model Usage Pie */}
        <div className="animate-fade-in" style={{ animationDelay: '0.3s' }}>
          <ChartCard
            title="Model Usage"
            subtitle="Distribution by provider"
            height={260}
          >
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={modelUsageData}
                  cx="50%"
                  cy="50%"
                  innerRadius={60}
                  outerRadius={90}
                  paddingAngle={2}
                  dataKey="value"
                >
                  {modelUsageData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip 
                  contentStyle={{
                    background: 'var(--bg-card)',
                    border: '1px solid var(--border-color)',
                    borderRadius: '8px',
                    color: 'var(--text-primary)'
                  }}
                  formatter={(value: number) => [`${value}%`, 'Usage']}
                />
              </PieChart>
            </ResponsiveContainer>
            <div className="flex flex-wrap justify-center gap-3 mt-2">
              {modelUsageData.map((item) => (
                <div key={item.name} className="flex items-center gap-1.5">
                  <div 
                    className="w-2.5 h-2.5 rounded-full"
                    style={{ background: item.color }}
                  />
                  <span className="text-xs">
                    {item.name}
                  </span>
                </div>
              ))}
            </div>
          </ChartCard>
        </div>
      </div>

      {/* Bottom Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {/* Recent Activity */}
        <div className="animate-fade-in" style={{ animationDelay: '0.4s' }}>
          <div className="glass-card p-5">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-base font-semibold">
                Recent Activity
              </h3>
              <button className="text-sm hover:underline"
              >
                View All
              </button>
            </div>
            <ActivityFeed items={recentActivity} maxItems={5} />
          </div>
        </div>

        {/* Quick Stats */}
        <div className="animate-fade-in" style={{ animationDelay: '0.5s' }}>
          <div className="glass-card p-5">
            <h3 className="text-base font-semibold mb-4">
              Quick Statistics
            </h3>
            <div className="space-y-4">
              <div className="flex items-center justify-between p-3 rounded-lg" style={{ background: 'var(--bg-secondary)' }}>
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-lg flex items-center justify-center" style={{ background: 'rgba(0,212,255,0.1)' }}>
                    <BenchmarkIcon className="w-5 h-5" />
                  </div>
                  <span className="text-sm">Total Benchmarks</span>
                </div>
                <span className="text-lg font-bold">
                  {overview?.total_benchmarks?.toLocaleString() || 0}
                </span>
              </div>
              
              <div className="flex items-center justify-between p-3 rounded-lg" style={{ background: 'var(--bg-secondary)' }}>
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-lg flex items-center justify-center" style={{ background: 'rgba(120,86,255,0.1)' }}>
                    <CapabilityIcon className="w-5 h-5" />
                  </div>
                  <span className="text-sm">Capabilities</span>
                </div>
                <span className="text-lg font-bold">
                  {overview?.total_capabilities || 0}
                </span>
              </div>
              
              <div className="flex items-center justify-between p-3 rounded-lg" style={{ background: 'var(--bg-secondary)' }}>
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-lg flex items-center justify-center" style={{ background: 'rgba(0,186,124,0.1)' }}>
                    <EvidenceIcon className="w-5 h-5" />
                  </div>
                  <span className="text-sm">Evidence Records</span>
                </div>
                <span className="text-lg font-bold">
                  {overview?.total_evidence_records || 0}
                </span>
              </div>
              
              <div className="flex items-center justify-between p-3 rounded-lg" style={{ background: 'var(--bg-secondary)' }}>
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-lg flex items-center justify-center" style={{ background: 'rgba(29,155,240,0.1)' }}>
                    <RouteIcon className="w-5 h-5" />
                  </div>
                  <span className="text-sm">SubAgent Routes</span>
                </div>
                <span className="text-lg font-bold">
                  {overview?.total_subagent_routes || 0}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Quick Actions */}
      <div className="animate-fade-in" style={{ animationDelay: '0.6s' }}>
        <h3 className="text-base font-semibold mb-4">
          Quick Actions
        </h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <button 
            className="glass-card p-4 flex flex-col items-center gap-3 hover:scale-[1.02] transition-transform"
            onClick={() => navigate('/models')}
          >
            <div className="w-12 h-12 rounded-xl flex items-center justify-center" style={{ background: 'rgba(29,155,240,0.1)' }}>
              <ModelIcon className="w-6 h-6" />
            </div>
            <span className="text-sm font-medium">Browse Models</span>
          </button>
          
          <button 
            className="glass-card p-4 flex flex-col items-center gap-3 hover:scale-[1.02] transition-transform"
            onClick={() => navigate('/benchmarks')}
          >
            <div className="w-12 h-12 rounded-xl flex items-center justify-center" style={{ background: 'rgba(0,212,255,0.1)' }}>
              <BenchmarkIcon className="w-6 h-6" />
            </div>
            <span className="text-sm font-medium">View Benchmarks</span>
          </button>
          
          <button 
            className="glass-card p-4 flex flex-col items-center gap-3 hover:scale-[1.02] transition-transform"
            onClick={() => navigate('/routing')}
          >
            <div className="w-12 h-12 rounded-xl flex items-center justify-center" style={{ background: 'rgba(120,86,255,0.1)' }}>
              <RouteIcon className="w-6 h-6" />
            </div>
            <span className="text-sm font-medium">Check Routing</span>
          </button>
          
          <button 
            className="glass-card p-4 flex flex-col items-center gap-3 hover:scale-[1.02] transition-transform"
            onClick={() => navigate('/health')}
          >
            <div className="w-12 h-12 rounded-xl flex items-center justify-center" style={{ background: 'rgba(0,186,124,0.1)' }}>
              <HeartIcon className="w-6 h-6" />
            </div>
            <span className="text-sm font-medium">System Health</span>
          </button>
        </div>
      </div>
    </div>
  );
}

// Icon Components
function ModelIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <rect x="4" y="4" width="16" height="16" rx="2" />
      <rect x="9" y="9" width="6" height="6" />
      <line x1="9" y1="1" x2="9" y2="4" />
      <line x1="15" y1="1" x2="15" y2="4" />
      <line x1="9" y1="20" x2="9" y2="23" />
      <line x1="15" y1="20" x2="15" y2="23" />
    </svg>
  );
}

function CloudIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M18 10h-1.26A8 8 0 1 0 9 20h9a5 5 0 0 0 0-10z" />
    </svg>
  );
}

function TaskIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M9 11l3 3L22 4" />
      <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" />
    </svg>
  );
}

function CheckIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <polyline points="20 6 9 17 4 12" />
    </svg>
  );
}

function HeartIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z" />
    </svg>
  );
}

function RefreshIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M23 4v6h-6" />
      <path d="M1 20v-6h6" />
      <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
    </svg>
  );
}

function PlayIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <polygon points="5 3 19 12 5 21 5 3" />
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

function CapabilityIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
    </svg>
  );
}

function EvidenceIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <polyline points="14 2 14 8 20 8" />
      <line x1="16" y1="13" x2="8" y2="13" />
      <line x1="16" y1="17" x2="8" y2="17" />
    </svg>
  );
}

function RouteIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <circle cx="12" cy="12" r="3" />
      <path d="M12 2v4m0 12v4M2 12h4m12 0h4" />
    </svg>
  );
}
