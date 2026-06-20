import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiClient } from '../api/client';
import type { ProviderSummary } from '../types';
import Badge from '../components/Badge';

export default function ProvidersPage() {
  const navigate = useNavigate();
  const [providers, setProviders] = useState<ProviderSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const loadData = async () => {
      try {
        setLoading(true);
        setError(null);
        const data = await apiClient.getProviders().catch(() => []);
        setProviders(data || []);
      } catch (err) {
        setError('Failed to load providers');
        console.error('Failed to load providers:', err);
      } finally {
        setLoading(false);
      }
    };
    loadData();
  }, []);

  const getHealthVariant = (score: number) => {
    if (score >= 80) return 'success';
    if (score >= 50) return 'warning';
    return 'danger';
  };

  const getTrustBadge = (level: number) => {
    if (level >= 80) return { label: 'High Trust', variant: 'success' as const };
    if (level >= 50) return { label: 'Medium Trust', variant: 'warning' as const };
    return { label: 'Low Trust', variant: 'danger' as const };
  };

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="skeleton h-12 w-64 rounded-lg" />
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {[...Array(6)].map((_, i) => (
            <div key={i} className="skeleton h-48 rounded-2xl" />
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold gradient-text">Providers</h1>
          <p className="text-sm mt-1">
            Manage and monitor your model providers
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

  if (providers.length === 0) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold gradient-text">Providers</h1>
          <p className="text-sm mt-1">
            Manage and monitor your model providers
          </p>
        </div>
        <div className="text-center py-16">
          <div className="w-16 h-16 rounded-full mx-auto mb-4 flex items-center justify-center" style={{ background: 'rgba(0,212,255,0.1)' }}>
            <CloudIcon className="w-8 h-8 text-gray-500" />
          </div>
          <h2 className="text-xl font-semibold mb-2">No Providers Configured</h2>
          <p className="text-sm text-gray-500">Add your first provider to get started.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div>
        <h1 className="text-2xl font-bold gradient-text">Providers</h1>
        <p className="text-sm mt-1">
          Manage and monitor your model providers • {providers.length} providers configured
        </p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="glass-card p-5">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 rounded-xl flex items-center justify-center" style={{ background: 'rgba(0,212,255,0.1)' }}>
              <CloudIcon className="w-6 h-6" />
            </div>
            <div>
              <p className="text-2xl font-bold">{providers.length}</p>
              <p className="text-sm">Total Providers</p>
            </div>
          </div>
        </div>
        <div className="glass-card p-5">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 rounded-xl flex items-center justify-center" style={{ background: 'rgba(0,186,124,0.1)' }}>
              <CheckIcon className="w-6 h-6" />
            </div>
            <div>
              <p className="text-2xl font-bold">
                {providers.filter(p => p.health_score >= 80).length}
              </p>
              <p className="text-sm">Healthy Providers</p>
            </div>
          </div>
        </div>
        <div className="glass-card p-5">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 rounded-xl flex items-center justify-center" style={{ background: 'rgba(120,86,255,0.1)' }}>
              <ModelIcon className="w-6 h-6" />
            </div>
            <div>
              <p className="text-2xl font-bold">
                {providers.reduce((sum, p) => sum + p.model_count, 0)}
              </p>
              <p className="text-sm">Total Models</p>
            </div>
          </div>
        </div>
      </div>

      {/* Providers Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
        {providers.map((provider, index) => {
          const trust = getTrustBadge(provider.trust_level);
          return (
            <div
              key={provider.provider_id}
              className="glass-card p-5 cursor-pointer animate-fade-in"
              style={{ animationDelay: `${index * 50}ms` }}
              onClick={() => navigate(`/models?provider=${encodeURIComponent(provider.display_name || provider.provider_id)}`)}
            >
              {/* Header */}
              <div className="flex items-start justify-between mb-4">
                <div className="flex items-center gap-3">
                  <div 
                    className="w-14 h-14 rounded-xl flex items-center justify-center text-xl font-bold"
                    style={{ background: 'linear-gradient(135deg, var(--accent-cyan), var(--accent-blue))' }}
                  >
                    {provider.display_name?.charAt(0) || provider.provider_id.charAt(0)}
                  </div>
                  <div>
                    <h3 className="font-semibold text-lg">
                      {provider.display_name || provider.provider_id}
                    </h3>
                    <p className="text-xs">
                      {provider.source_type}
                    </p>
                  </div>
                </div>
                {provider.api_key_present && (
                  <div className="w-3 h-3 rounded-full" style={{ background: 'var(--accent-green)', boxShadow: '0 0 8px var(--accent-green)' }} />
                )}
              </div>

              {/* Stats */}
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-sm">Models</span>
                  <span className="font-semibold">{provider.model_count}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm">Health Score</span>
                  <div className="flex items-center gap-2">
                    <div className="w-20 h-2 rounded-full" style={{ background: 'var(--bg-secondary)' }}>
                      <div 
                        className="h-full rounded-full"
                        style={{ 
                          width: `${provider.health_score}%`,
                          background: provider.health_score >= 80 ? 'var(--accent-green)' : provider.health_score >= 50 ? 'var(--accent-yellow)' : 'var(--accent-red)'
                        }}
                      />
                    </div>
                    <span className="text-sm font-medium">{provider.health_score}%</span>
                  </div>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm">Trust Level</span>
                  <Badge label={trust.label} variant={trust.variant} />
                </div>
              </div>

              {/* Footer */}
              <div className="flex items-center justify-between mt-4 pt-4 border-t" style={{ borderColor: 'var(--border-color)' }}>
                <div className="flex items-center gap-2">
                  <Badge label={provider.api_key_present ? 'API Key' : 'No API Key'} 
                         variant={provider.api_key_present ? 'success' : 'warning'} size="sm" />
                </div>
                <span className="text-xs">
                  View Models →
                </span>
              </div>
            </div>
          );
        })}
      </div>

      {providers.length === 0 && (
        <div className="text-center py-16">
          <div className="w-16 h-16 rounded-full mx-auto mb-4 flex items-center justify-center" style={{ background: 'rgba(0,212,255,0.1)' }}>
            <CloudIcon className="w-8 h-8" />
          </div>
          <h2 className="text-xl font-semibold mb-2">No Providers Configured</h2>
          <p className="text-sm">Add your first provider to get started.</p>
        </div>
      )}
    </div>
  );
}

// Icons
function CloudIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M18 10h-1.26A8 8 0 1 0 9 20h9a5 5 0 0 0 0-10z" />
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

function ModelIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <rect x="4" y="4" width="16" height="16" rx="2" />
      <rect x="9" y="9" width="6" height="6" />
    </svg>
  );
}
