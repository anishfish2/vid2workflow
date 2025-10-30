'use client';

import { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';

interface Workflow {
  id: string;
  name: string;
  description?: string;
  video_key?: string;
  status: string;
  created_at: string;
  updated_at: string;
  n8n_workflow_id?: string;
  steps: any[];
  n8n_workflow_data?: any;
}

export default function WorkflowDetailPage() {
  const params = useParams();
  const router = useRouter();
  const [workflow, setWorkflow] = useState<Workflow | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchWorkflow();
  }, [params.id]);

  const fetchWorkflow = async () => {
    const token = localStorage.getItem('auth_token');

    if (!token) {
      setError('Please log in to view this workflow');
      setLoading(false);
      return;
    }

    try {
      const response = await fetch(`http://localhost:8000/workflows/${params.id}`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });

      if (!response.ok) {
        throw new Error('Failed to fetch workflow');
      }

      const data = await response.json();
      setWorkflow(data.workflow);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load workflow');
    } finally {
      setLoading(false);
    }
  };

  const openInN8n = () => {
    if (workflow?.n8n_workflow_id) {
      window.open(`http://localhost:5678/workflow/${workflow.n8n_workflow_id}`, '_blank');
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div>Loading workflow...</div>
      </div>
    );
  }

  if (error || !workflow) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="text-red-500 mb-4">{error || 'Workflow not found'}</div>
          <button
            onClick={() => router.push('/')}
            className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
          >
            Back to Home
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen p-8">
      <div className="max-w-4xl mx-auto">
        {/* Header */}
        <div className="mb-6">
          <button
            onClick={() => router.push('/')}
            className="mb-4 text-blue-500 hover:text-blue-600"
          >
            ← Back to Workflows
          </button>
          <div className="flex justify-between items-start">
            <div>
              <h1 className="text-3xl font-bold mb-2">{workflow.name}</h1>
              {workflow.description && (
                <p className="text-gray-600">{workflow.description}</p>
              )}
            </div>
            <span
              className={`px-3 py-1 rounded ${
                workflow.status === 'active'
                  ? 'bg-green-100 text-green-700'
                  : workflow.status === 'draft'
                  ? 'bg-yellow-100 text-yellow-700'
                  : 'bg-gray-100 text-gray-700'
              }`}
            >
              {workflow.status}
            </span>
          </div>
        </div>

        {/* Metadata */}
        <div className="bg-gray-50 rounded-lg p-4 mb-6">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <div className="text-sm text-gray-500">Created</div>
              <div className="font-medium">
                {new Date(workflow.created_at).toLocaleString()}
              </div>
            </div>
            <div>
              <div className="text-sm text-gray-500">Last Updated</div>
              <div className="font-medium">
                {new Date(workflow.updated_at).toLocaleString()}
              </div>
            </div>
            {workflow.video_key && (
              <div>
                <div className="text-sm text-gray-500">Source Video</div>
                <div className="font-medium truncate">
                  {workflow.video_key.split('/').pop()}
                </div>
              </div>
            )}
            {workflow.n8n_workflow_id && (
              <div>
                <div className="text-sm text-gray-500">n8n Workflow ID</div>
                <div className="font-medium">{workflow.n8n_workflow_id}</div>
              </div>
            )}
          </div>

          {workflow.n8n_workflow_id && (
            <button
              onClick={openInN8n}
              className="mt-4 w-full px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
            >
              Open in n8n
            </button>
          )}
        </div>

        {/* Steps */}
        <div className="mb-6">
          <h2 className="text-xl font-semibold mb-4">Workflow Steps ({workflow.steps?.length || 0})</h2>
          <div className="space-y-3">
            {workflow.steps && workflow.steps.length > 0 ? (
              workflow.steps.map((step, index) => (
                <div key={index} className="border rounded-lg p-4 bg-white">
                  <div className="flex items-start gap-3">
                    <div className="flex-shrink-0 w-8 h-8 bg-blue-500 text-white rounded-full flex items-center justify-center font-semibold">
                      {index + 1}
                    </div>
                    <div className="flex-1">
                      <h3 className="font-semibold mb-1">
                        {step.action || step.name || `Step ${index + 1}`}
                      </h3>
                      {step.service && (
                        <div className="text-sm text-gray-600 mb-2">
                          Service: <span className="font-medium">{step.service}</span>
                          {step.operation && ` → ${step.operation}`}
                        </div>
                      )}
                      {step.parameters && Object.keys(step.parameters).length > 0 && (
                        <div className="mt-2">
                          <div className="text-sm font-medium text-gray-700 mb-1">Parameters:</div>
                          <div className="bg-gray-50 rounded p-2 text-xs font-mono">
                            <pre className="whitespace-pre-wrap">
                              {JSON.stringify(step.parameters, null, 2)}
                            </pre>
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              ))
            ) : (
              <div className="text-gray-500 text-center py-4">No steps available</div>
            )}
          </div>
        </div>

        {/* Raw JSON (collapsible) */}
        <details className="border rounded-lg p-4 bg-white">
          <summary className="cursor-pointer font-semibold">
            View Raw Workflow Data
          </summary>
          <div className="mt-4 bg-gray-50 rounded p-4 overflow-auto">
            <pre className="text-xs font-mono">
              {JSON.stringify(workflow, null, 2)}
            </pre>
          </div>
        </details>
      </div>
    </div>
  );
}
