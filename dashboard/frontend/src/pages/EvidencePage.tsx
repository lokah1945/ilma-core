import { useEffect, useState } from 'react';
import { apiClient } from '../api/client';
import type { EvidenceItem } from '../types';
import Badge from '../components/Badge';

export default function EvidencePage() {
  const [evidence, setEvidence] = useState<EvidenceItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState('');

  useEffect(() => {
    const loadData = async () => {
      try {
        setLoading(true);
        setError(null);
        const data = await apiClient.getEvidence(statusFilter ? { status: statusFilter } : {});
        setEvidence(Array.isArray(data) ? data : data.items || []);
      } catch (err) {
        setError('Failed to load evidence data');
        console.error('Failed to load evidence:', err);
      } finally {
        setLoading(false);
      }
    };
    loadData();
  }, [statusFilter]);

  const statusColors: Record<string, string> = {
    VERIFIED: 'success',
    PASSED: 'success',
    FAILED: 'danger',
    UNVERIFIED: 'warning',
    BLOCKED: 'danger',
    DEPRECATED: 'default',
  };

  if (loading) {
    return (
      <div className="space-y-4">
        <div className="flex justify-between items-center">
          <div className="skeleton h-8 w-48 rounded" />
          <div className="skeleton h-8 w-32 rounded" />
        </div>
        <div className="skeleton h-4 w-32 rounded" />
        <div className="space-y-2">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="skeleton h-20 rounded-lg" />
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-4">
        <div className="flex justify-between items-center">
          <h1 className="text-2xl font-bold">Evidence Ledger</h1>
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
        <h1 className="text-2xl font-bold">Evidence Ledger</h1>
        <select
          value={statusFilter}
          onChange={e => setStatusFilter(e.target.value)}
          className="bg-gray-900 border border-gray-700 rounded px-3 py-1 text-sm"
        >
          <option value="">All statuses</option>
          <option value="VERIFIED">VERIFIED</option>
          <option value="PASSED">PASSED</option>
          <option value="FAILED">FAILED</option>
          <option value="UNVERIFIED">UNVERIFIED</option>
        </select>
      </div>

      <div className="text-sm text-gray-500">{evidence.length} records</div>

      {evidence.length === 0 ? (
        <div className="text-center py-16">
          <div className="w-16 h-16 rounded-full mx-auto mb-4 flex items-center justify-center" style={{ background: 'rgba(0,212,255,0.1)' }}>
            <DocumentIcon className="w-8 h-8 text-gray-500" />
          </div>
          <h2 className="text-xl font-semibold mb-2">No Evidence Records</h2>
          <p className="text-sm text-gray-500">No evidence found for the selected filter.</p>
        </div>
      ) : (
        <div className="space-y-2">
          {evidence.slice(0, 100).map(e => (
            <div key={e.evidence_id} className="bg-gray-900 rounded p-4 flex justify-between items-start">
              <div>
                <div className="text-sm font-medium">{e.evidence_id}</div>
                <div className="text-xs text-gray-500 mt-1">{e.claim || e.capability || 'No description'}</div>
              </div>
              <Badge
                label={e.status || 'UNKNOWN'}
                variant={(statusColors[e.status] || 'default') as 'success' | 'warning' | 'danger' | 'info' | 'purple' | 'default'}
              />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function DocumentIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <polyline points="14 2 14 8 20 8" />
      <line x1="16" y1="13" x2="8" y2="13" />
      <line x1="16" y1="17" x2="8" y2="17" />
      <polyline points="10 9 9 9 8 9" />
    </svg>
  );
}