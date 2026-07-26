import { useEffect, useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiClient } from '../api/client';
import type { ModelSummary } from '../types';
import DataTable from '../components/DataTable';
import Badge from '../components/Badge';
import StatCard from '../components/StatCard';

export default function ModelsPage() {
  const navigate = useNavigate();
  const [models, setModels] = useState<ModelSummary[]>([]);
  const [providers, setProviders] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedProvider, setSelectedProvider] = useState<string>('');

  useEffect(() => {
    const loadData = async () => {
      try {
        setLoading(true);
        setError(null);
        const [modelsData, providersData] = await Promise.all([
          apiClient.getModels().catch(() => []),
          apiClient.getProviders().catch(() => []),
        ]);
        setModels(modelsData);
        setProviders(providersData.map((p: { display_name?: string; provider_id: string }) => p.display_name || p.provider_id));
      } catch (err) {
        setError('Failed to load models');
        console.error('Failed to load models:', err);
      } finally {
        setLoading(false);
      }
    };
    loadData();
  }, []);

  const filteredModels = useMemo(() => {
    if (!selectedProvider) return models;
    return models.filter(m => m.provider === selectedProvider);
  }, [models, selectedProvider]);

  const getStatusVariant = (status: string) => {
    switch (status?.toLowerCase()) {
      case 'available':
      case 'active':
        return 'success';
      case 'limited':
      case 'degraded':
        return 'warning';
      case 'unavailable':
      case 'disabled':
        return 'danger';
      default:
        return 'info';
    }
  };

  const formatContextWindow = (tokens: number) => {
    if (!tokens) return 'N/A';
    if (tokens >= 1000000) return `${(tokens / 1000000).toFixed(1)}M`;
    if (tokens >= 1000) return `${(tokens / 1000).toFixed(0)}K`;
    return tokens.toString();
  };

  const columns = [
    {
      key: 'display_name',
      header: 'Model Name',
      sortable: true,
      render: (model: ModelSummary) => (
        <div className="flex items-center gap-3">
          <div 
            className="w-8 h-8 rounded-lg flex items-center justify-center text-xs font-bold"
            style={{ background: 'linear-gradient(135deg, var(--accent-cyan), var(--accent-blue))' }}
          >
            {model.display_name?.charAt(0) || '?'}
          </div>
          <div>
            <p className="font-medium">
              {model.display_name || 'Unknown'}
            </p>
            <p className="text-xs">
              {model.canonical_model_id || 'N/A'}
            </p>
          </div>
        </div>
      ),
    },
    {
      key: 'provider',
      header: 'Provider',
      sortable: true,
      render: (model: ModelSummary) => (
        <Badge label={model.provider || 'Unknown'} variant="info" />
      ),
    },
    {
      key: 'free_or_paid',
      header: 'Pricing',
      sortable: true,
      render: (model: ModelSummary) => (
        <Badge 
          label={model.free_or_paid === 'free' ? 'Free' : 'Paid'} 
          variant={model.free_or_paid === 'free' ? 'success' : 'warning'} 
        />
      ),
    },
    {
      key: 'context_window',
      header: 'Context Window',
      sortable: true,
      render: (model: ModelSummary) => (
        <span style={{ color: 'var(--text-secondary)' }}>
          {formatContextWindow(model.context_window)} tokens
        </span>
      ),
    },
    {
      key: 'availability_status',
      header: 'Status',
      sortable: true,
      render: (model: ModelSummary) => (
        <Badge 
          label={model.availability_status || 'Unknown'} 
          variant={getStatusVariant(model.availability_status)} 
          dot
        />
      ),
    },
    {
      key: 'supports_tools',
      header: 'Tools',
      sortable: false,
      render: (model: ModelSummary) => (
        model.supports_tools ? (
          <CheckCircleIcon className="w-5 h-5" />
        ) : (
          <XCircleIcon className="w-5 h-5" />
        )
      ),
    },
    {
      key: 'actions',
      header: '',
      sortable: false,
      render: (model: ModelSummary) => (
        <button 
          className="p-2 rounded-lg hover:bg-[var(--bg-card)] transition-colors"
          onClick={(e) => {
            e.stopPropagation();
            navigate(`/models/${encodeURIComponent(model.canonical_model_id || '')}`);
          }}
        >
          <ArrowRightIcon className="w-4 h-4" />
        </button>
      ),
    },
  ];

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="skeleton h-12 w-64 rounded-lg" />
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="skeleton h-28 rounded-xl" />
          ))}
        </div>
        <div className="skeleton h-96 rounded-xl" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold gradient-text">Models</h1>
            <p className="text-sm mt-1">Browse and manage all registered models</p>
          </div>
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

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold gradient-text">Models</h1>
          <p className="text-sm mt-1">
            Browse and manage all {models.length} registered models
          </p>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <StatCard
          title="Total Models"
          value={models.length}
          variant="info"
          icon={<ModelIcon />}
        />
        <StatCard
          title="Free Models"
          value={models.filter(m => m.free_or_paid === 'free').length}
          variant="success"
          icon={<CheckIcon />}
        />
        <StatCard
          title="Paid Models"
          value={models.filter(m => m.free_or_paid === 'paid').length}
          variant="warning"
          icon={<DollarIcon />}
        />
        <StatCard
          title="Providers"
          value={providers.length}
          variant="default"
          icon={<CloudIcon />}
        />
      </div>

      {/* Filters */}
      <div className="flex items-center gap-4">
        <select
          value={selectedProvider}
          onChange={(e) => setSelectedProvider(e.target.value)}
          className="input-field w-48"
        >
          <option value="">All Providers</option>
          {providers.map(p => (
            <option key={p} value={p}>{p}</option>
          ))}
        </select>
        
        {selectedProvider && (
          <button
            onClick={() => setSelectedProvider('')}
            className="text-sm hover:underline"
            style={{ color: 'var(--accent-cyan)' }}
          >
            Clear filter
          </button>
        )}
      </div>

      {/* Table */}
      <DataTable
        columns={columns}
        data={filteredModels}
        keyExtractor={(m) => m.canonical_model_id}
        onRowClick={(model) => navigate(`/models/${encodeURIComponent(model.canonical_model_id || '')}`)}
        loading={loading}
        emptyMessage="No models found"
        pageSize={20}
      />
    </div>
  );
}

// Icons
function ModelIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <rect x="4" y="4" width="16" height="16" rx="2" />
      <rect x="9" y="9" width="6" height="6" />
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

function DollarIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <line x1="12" y1="1" x2="12" y2="23" />
      <path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6" />
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

function CheckCircleIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
      <polyline points="22 4 12 14.01 9 11.01" />
    </svg>
  );
}

function XCircleIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <circle cx="12" cy="12" r="10" />
      <line x1="15" y1="9" x2="9" y2="15" />
      <line x1="9" y1="9" x2="15" y2="15" />
    </svg>
  );
}

function ArrowRightIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <line x1="5" y1="12" x2="19" y2="12" />
      <polyline points="12 5 19 12 12 19" />
    </svg>
  );
}
