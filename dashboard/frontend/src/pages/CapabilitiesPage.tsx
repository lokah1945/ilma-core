import { useEffect, useState } from 'react';
import { apiClient } from '../api/client';
import type { CapabilityItem } from '../types';
import Badge from '../components/Badge';

export default function CapabilitiesPage() {
  const [capabilities, setCapabilities] = useState<CapabilityItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState('');

  useEffect(() => {
    const loadData = async () => {
      try {
        setLoading(true);
        setError(null);
        const data = await apiClient.getCapabilities(statusFilter || undefined);
        setCapabilities(data.items || []);
      } catch (err) {
        setError('Failed to load capabilities');
        console.error('Failed to load capabilities:', err);
      } finally {
        setLoading(false);
      }
    };
    loadData();
  }, [statusFilter]);

  const statusColors: Record<string, string> = {
    VERIFIED: 'success',
    STRONGLY_SUPPORTED: 'success',
    PARTIAL: 'warning',
    UNVERIFIED: 'warning',
    BLOCKED: 'danger',
    DEPRECATED: 'default',
  };

  if (loading) {
    return (
      <div className="space-y-4">
        <div className="flex justify-between items-center">
          <div className="skeleton h-8 w-48 rounded" />
          <div className="skeleton h-8 w-40 rounded" />
        </div>
        <div className="skeleton h-4 w-36 rounded" />
        <div className="grid grid-cols-2 gap-3">
          {[...Array(6)].map((_, i) => (
            <div key={i} className="skeleton h-24 rounded-lg" />
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-4">
        <div className="flex justify-between items-center">
          <h1 className="text-2xl font-bold">Capability Registry</h1>
        </div>
        <div className="bg-red-900/20 border border-red-800 rounded-lg p-6 text-center">
          <p className="text-red-400">{error}</p>
          <button
            onClick={() => setStatusFilter(statusFilter)}
            className="mt-3 px-4 py-2 bg-red-800 hover:bg-red-700 rounded text-sm"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold">Capability Registry</h1>
        <select
          value={statusFilter}
          onChange={e => setStatusFilter(e.target.value)}
          className="bg-gray-900 border border-gray-700 rounded px-3 py-1 text-sm"
        >
          <option value="">All statuses</option>
          <option value="VERIFIED">VERIFIED</option>
          <option value="STRONGLY_SUPPORTED">STRONGLY_SUPPORTED</option>
          <option value="PARTIAL">PARTIAL</option>
          <option value="UNVERIFIED">UNVERIFIED</option>
          <option value="BLOCKED">BLOCKED</option>
        </select>
      </div>

      <div className="text-sm text-gray-500">{capabilities.length} capabilities</div>

      {capabilities.length === 0 ? (
        <div className="text-center py-16">
          <div className="w-16 h-16 rounded-full mx-auto mb-4 flex items-center justify-center" style={{ background: 'rgba(120,86,255,0.1)' }}>
            <CapabilityIcon className="w-8 h-8 text-gray-500" />
          </div>
          <h2 className="text-xl font-semibold mb-2">No Capabilities Found</h2>
          <p className="text-sm text-gray-500">No capabilities match the selected filter.</p>
        </div>
      ) : (
        <div className="grid grid-cols-2 gap-3">
          {capabilities.map(c => (
            <div key={c.capability_id} className="bg-gray-900 rounded p-4">
              <div className="flex justify-between items-start mb-2">
                <h3 className="text-sm font-semibold">{c.capability_id}</h3>
                <Badge
                  label={c.status || 'UNVERIFIED'}
                  variant={(statusColors[c.status] || 'default') as 'success' | 'warning' | 'danger' | 'info' | 'purple' | 'default'}
                />
              </div>
              <div className="text-xs text-gray-500">{c.category || 'N/A'}</div>
              {c.caveat && <div className="text-xs text-yellow-400 mt-1">{c.caveat}</div>}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function CapabilityIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <circle cx="12" cy="12" r="10" />
      <circle cx="12" cy="12" r="6" />
      <circle cx="12" cy="12" r="2" />
    </svg>
  );
}