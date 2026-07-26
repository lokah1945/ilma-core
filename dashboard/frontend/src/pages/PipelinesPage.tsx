import { useEffect, useState } from 'react';
import { apiClient } from '../api/client';
import type { WorkflowItem } from '../types';

export default function PipelinesPage() {
  const [pipelines, setPipelines] = useState<WorkflowItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const loadData = async () => {
      try {
        setLoading(true);
        setError(null);
        const data = await apiClient.getWorkflows();
        const all = Array.isArray(data) ? data : data.items || [];
        setPipelines(all.filter((w: WorkflowItem) => w.pipeline_stages));
      } catch (err) {
        setError('Failed to load pipelines');
        console.error('Failed to load pipelines:', err);
      } finally {
        setLoading(false);
      }
    };
    loadData();
  }, []);

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="skeleton h-8 w-32 rounded" />
        <div className="space-y-4">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="skeleton h-28 rounded-lg" />
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold">Pipelines</h1>
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

  if (pipelines.length === 0) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold">Pipelines</h1>
        <div className="text-center py-16">
          <div className="w-16 h-16 rounded-full mx-auto mb-4 flex items-center justify-center" style={{ background: 'rgba(0,212,255,0.1)' }}>
            <PipelineIcon className="w-8 h-8 text-gray-500" />
          </div>
          <h2 className="text-xl font-semibold mb-2">No Pipelines Found</h2>
          <p className="text-sm text-gray-500">No pipeline definitions are available.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Pipelines</h1>

      {pipelines.map(p => {
        let stages: string[] = [];
        try { stages = JSON.parse(p.pipeline_stages || '[]'); } catch {}

        return (
          <div key={p.workflow_id} className="bg-gray-900 rounded-lg overflow-hidden">
            <div className="px-4 py-3 border-b border-gray-800">
              <h2 className="font-semibold">{p.workflow_name}</h2>
              <p className="text-xs text-gray-500">{p.workflow_id}</p>
            </div>
            <div className="p-4">
              <div className="flex items-center gap-2 flex-wrap">
                {stages.length > 0 ? stages.map((s, i) => (
                  <div key={i} className="flex items-center gap-2">
                    <span className="w-6 h-6 rounded-full bg-blue-700 text-white text-xs flex items-center justify-center font-bold">
                      {i + 1}
                    </span>
                    <span className="text-sm text-blue-300 bg-gray-800 rounded px-2 py-1">{s}</span>
                    {i < stages.length - 1 && (
                      <span className="text-gray-600">→</span>
                    )}
                  </div>
                )) : (
                  <span className="text-sm text-gray-500">No stages defined</span>
                )}
              </div>
            </div>
            {p.tools_used && (
              <div className="px-4 py-2 border-t border-gray-800 text-xs text-gray-400">
                Tools: {p.tools_used}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

function PipelineIcon({ className }: { className?: string }) {
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