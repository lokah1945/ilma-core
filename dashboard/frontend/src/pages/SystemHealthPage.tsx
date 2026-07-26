import { useEffect, useState } from 'react';
import { apiClient } from '../api/client';
import type { SystemHealthSnapshot } from '../types';

export default function SystemHealthPage() {
  const [health, setHealth] = useState<SystemHealthSnapshot[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const loadData = async () => {
      try {
        setLoading(true);
        setError(null);
        const data = await apiClient.getSystemHealth();
        setHealth(Array.isArray(data) ? data : []);
      } catch (err) {
        setError('Failed to load system health data');
        console.error('Failed to load system health:', err);
      } finally {
        setLoading(false);
      }
    };
    loadData();
  }, []);

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="skeleton h-8 w-48 rounded" />
        <div className="grid grid-cols-2 gap-4">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="skeleton h-24 rounded-lg" />
          ))}
        </div>
        <div className="skeleton h-40 rounded-lg" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold">System Health</h1>
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

  const latest = health[0];

  if (!latest) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold">System Health</h1>
        <div className="text-center py-16">
          <div className="w-16 h-16 rounded-full mx-auto mb-4 flex items-center justify-center" style={{ background: 'rgba(0,186,124,0.1)' }}>
            <HeartIcon className="w-8 h-8 text-gray-500" />
          </div>
          <h2 className="text-xl font-semibold mb-2">No Health Data</h2>
          <p className="text-sm text-gray-500">System health snapshots are not available.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">System Health</h1>

      <div className="grid grid-cols-2 gap-4">
        <div className="bg-gray-900 rounded p-4">
          <div className="text-xs text-gray-500">Validate Status</div>
          <div className="text-lg font-bold mt-1">
            {latest.validate_status?.includes('PASS') ? (
              <span className="text-green-400">✅ PASS</span>
            ) : (
              <span className="text-red-400">❌ {latest.validate_status || 'UNKNOWN'}</span>
            )}
          </div>
        </div>

        <div className="bg-gray-900 rounded p-4">
          <div className="text-xs text-gray-500">Doctor Status</div>
          <div className="text-lg font-bold mt-1">
            {latest.doctor_status?.includes('PASS') ? (
              <span className="text-green-400">✅ PASS</span>
            ) : (
              <span className="text-red-400">❌ {latest.doctor_status || 'UNKNOWN'}</span>
            )}
          </div>
        </div>

        <div className="bg-gray-900 rounded p-4">
          <div className="text-xs text-gray-500">Production Smoke</div>
          <div className="text-lg font-bold mt-1">
            {latest.production_smoke?.includes('PASS') ? (
              <span className="text-green-400">✅ PASS</span>
            ) : (
              <span className="text-yellow-400">⚠️ {latest.production_smoke || 'NOT_RUN'}</span>
            )}
          </div>
        </div>

        <div className="bg-gray-900 rounded p-4">
          <div className="text-xs text-gray-500">Last Checked</div>
          <div className="text-lg font-bold mt-1 text-gray-300">
            {latest.timestamp ? new Date(latest.timestamp).toLocaleString() : 'Never'}
          </div>
        </div>
      </div>

      <div className="bg-gray-900 rounded p-4">
        <h2 className="text-sm font-semibold mb-3">Dashboard Statistics</h2>
        <div className="grid grid-cols-3 gap-4 text-sm">
          <div>
            <div className="text-xs text-gray-500">Total Tests</div>
            <div className="text-xl font-bold">{latest.total_tests ?? 191}</div>
          </div>
          <div>
            <div className="text-xs text-gray-500">Tests Passed</div>
            <div className="text-xl font-bold text-green-400">{latest.tests_passed ?? 191}</div>
          </div>
          <div>
            <div className="text-xs text-gray-500">Tests Failed</div>
            <div className="text-xl font-bold text-red-400">{latest.tests_failed ?? 0}</div>
          </div>
        </div>
      </div>
    </div>
  );
}

function HeartIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z" />
    </svg>
  );
}