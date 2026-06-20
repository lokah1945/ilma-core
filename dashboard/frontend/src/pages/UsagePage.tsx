import { useEffect, useState } from 'react';
import { apiClient } from '../api/client';
import type { UsageSummary, DailyUsageItem } from '../types';

export default function UsagePage() {
  const [summary, setSummary] = useState<UsageSummary | null>(null);
  const [daily, setDaily] = useState<DailyUsageItem[]>([]);
  const [period, setPeriod] = useState<'today' | 'week' | 'month'>('month');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const loadData = async () => {
      try {
        setLoading(true);
        setError(null);
        const [sum, d] = await Promise.all([
          apiClient.getUsageSummary({ period }),
          apiClient.getDailyUsage({}),
        ]);
        setSummary(sum);
        setDaily(d.items || []);
      } catch (err) {
        setError('Failed to load usage data');
        console.error('Failed to load usage:', err);
      } finally {
        setLoading(false);
      }
    };
    loadData();
  }, [period]);

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="flex justify-between items-center">
          <div className="skeleton h-8 w-40 rounded" />
          <div className="flex gap-2">
            {[...Array(3)].map((_, i) => (
              <div key={i} className="skeleton h-8 w-16 rounded" />
            ))}
          </div>
        </div>
        <div className="grid grid-cols-3 gap-4">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="skeleton h-20 rounded-lg" />
          ))}
        </div>
        <div className="skeleton h-48 rounded-lg" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-6">
        <div className="flex justify-between items-center">
          <h1 className="text-2xl font-bold">Token Usage</h1>
        </div>
        <div className="bg-red-900/20 border border-red-800 rounded-lg p-6 text-center">
          <p className="text-red-400">{error}</p>
          <button
            onClick={() => setPeriod(period)}
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
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold">Token Usage</h1>
        <div className="flex gap-2">
          {(['today', 'week', 'month'] as const).map(p => (
            <button
              key={p}
              onClick={() => setPeriod(p)}
              className={`px-3 py-1 rounded text-sm ${
                period === p ? 'bg-blue-700 text-white' : 'bg-gray-800 text-gray-400'
              }`}
            >
              {p}
            </button>
          ))}
        </div>
      </div>

      {summary && (
        <div className="grid grid-cols-3 gap-4">
          <div className="bg-gray-900 rounded p-4">
            <div className="text-xs text-gray-500">Total Requests</div>
            <div className="text-2xl font-bold">{summary.total_requests?.toLocaleString() ?? 0}</div>
          </div>
          <div className="bg-gray-900 rounded p-4">
            <div className="text-xs text-gray-500">Total Tokens</div>
            <div className="text-2xl font-bold">{summary.total_tokens?.toLocaleString() ?? 0}</div>
          </div>
          <div className="bg-gray-900 rounded p-4">
            <div className="text-xs text-gray-500">Estimated Cost</div>
            <div className="text-2xl font-bold">${summary.total_cost?.toFixed(4) ?? '0'}</div>
          </div>
        </div>
      )}

      {daily.length > 0 ? (
        <div>
          <h2 className="text-lg font-semibold mb-3">Daily History</h2>
          <div className="space-y-1">
            {daily.map((d) => (
              <div key={d.date} className="bg-gray-900 rounded px-4 py-2 flex justify-between text-sm">
                <span className="text-gray-400">{d.date}</span>
                <span>{d.total_tokens?.toLocaleString() ?? 0} tokens</span>
                <span className="text-gray-500">{d.total_requests ?? 0} requests</span>
                <span className="text-green-400">${d.total_cost?.toFixed(4) ?? '0'}</span>
              </div>
            ))}
          </div>
        </div>
      ) : (
        <div className="text-center py-16">
          <div className="w-16 h-16 rounded-full mx-auto mb-4 flex items-center justify-center" style={{ background: 'rgba(0,212,255,0.1)' }}>
            <ChartIcon className="w-8 h-8 text-gray-500" />
          </div>
          <h2 className="text-xl font-semibold mb-2">No Usage Data</h2>
          <p className="text-sm text-gray-500">No usage data available for this period.</p>
        </div>
      )}
    </div>
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