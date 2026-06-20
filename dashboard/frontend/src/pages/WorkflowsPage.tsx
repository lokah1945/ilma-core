import { useEffect, useState } from 'react';
import { apiClient } from '../api/client';
import type { WorkflowItem } from '../types';

export default function WorkflowsPage() {
  const [workflows, setWorkflows] = useState<WorkflowItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const loadData = async () => {
      try {
        setLoading(true);
        setError(null);
        const data = await apiClient.getWorkflows();
        setWorkflows(Array.isArray(data) ? data : data.items || []);
      } catch (err) {
        setError('Failed to load workflows');
        console.error('Failed to load workflows:', err);
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
            <div key={i} className="skeleton h-32 rounded-lg" />
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold">Workflows</h1>
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

  if (workflows.length === 0) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold">Workflows</h1>
        <div className="text-center py-16">
          <div className="w-16 h-16 rounded-full mx-auto mb-4 flex items-center justify-center" style={{ background: 'rgba(120,86,255,0.1)' }}>
            <WorkflowIcon className="w-8 h-8 text-gray-500" />
          </div>
          <h2 className="text-xl font-semibold mb-2">No Workflows Found</h2>
          <p className="text-sm text-gray-500">No workflow definitions are available.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Workflows</h1>

      {workflows.map(w => {
        let stages: string[] = [];
        try { stages = JSON.parse(w.pipeline_stages || '[]'); } catch {}

        return (
          <div key={w.workflow_id} className="bg-gray-900 rounded-lg overflow-hidden">
            <div className="px-4 py-3 border-b border-gray-800 flex justify-between items-center">
              <div>
                <h2 className="font-semibold">{w.workflow_name}</h2>
                <p className="text-xs text-gray-500">{w.workflow_id} • {w.trigger}</p>
              </div>
              <span className={`text-xs px-2 py-1 rounded ${
                w.status === 'ACTIVE' ? 'bg-green-900 text-green-300' : 'bg-gray-700 text-gray-400'
              }`}>
                {w.status}
              </span>
            </div>

            <div className="px-4 py-3">
              <div className="text-xs text-gray-500 mb-2">Pipeline Stages</div>
              <div className="flex flex-wrap gap-2">
                {stages.length > 0 ? stages.map((s, i) => (
                  <span key={i} className="text-xs bg-gray-800 rounded px-2 py-1 text-blue-300">
                    {i + 1}. {s}
                  </span>
                )) : (
                  <span className="text-xs text-gray-500">No stages defined</span>
                )}
              </div>
            </div>

            {w.tools_used && (
              <div className="px-4 py-2 border-t border-gray-800">
                <div className="text-xs text-gray-500 mb-1">Tools Used</div>
                <div className="text-xs text-gray-400">{w.tools_used}</div>
              </div>
            )}

            {w.model_routes && (
              <div className="px-4 py-2 border-t border-gray-800">
                <div className="text-xs text-gray-500 mb-1">Model Routes</div>
                <div className="text-xs text-green-400">{w.model_routes}</div>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

function WorkflowIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M9 11l3 3L22 4" />
      <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" />
    </svg>
  );
}