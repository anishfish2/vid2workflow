'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { executeWorkflow } from '@/lib/api';
import WorkflowEditChatModal from './WorkflowEditChatModal';

interface Workflow {
  id: string;
  name: string;
  description?: string;
  video_key?: string;
  status: string;
  created_at: string;
  n8n_workflow_id?: string;
  steps: any[];
}

export default function WorkflowList() {
  const [workflows, setWorkflows] = useState<Workflow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<string>('active');
  const [executingWorkflow, setExecutingWorkflow] = useState<string | null>(null);
  const [editingWorkflow, setEditingWorkflow] = useState<Workflow | null>(null);
  const router = useRouter();

  useEffect(() => {
    fetchWorkflows();
  }, [filter]);

  const fetchWorkflows = async () => {
    const token = localStorage.getItem('auth_token');

    if (!token) {
      setError('Please log in to view your workflows');
      setLoading(false);
      return;
    }

    try {
      setLoading(true);
      const url = filter
        ? `http://localhost:8000/workflows/?status=${filter}`
        : 'http://localhost:8000/workflows/';

      const response = await fetch(url, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });

      if (!response.ok) {
        throw new Error('Failed to fetch workflows');
      }

      const data = await response.json();
      setWorkflows(data.workflows);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load workflows');
    } finally {
      setLoading(false);
    }
  };

  const deleteWorkflow = async (workflowId: string) => {
    if (!confirm('Are you sure you want to delete this workflow?')) {
      return;
    }

    const token = localStorage.getItem('auth_token');
    if (!token) return;

    try {
      const response = await fetch(`http://localhost:8000/workflows/${workflowId}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });

      if (response.ok) {
        // Refresh the list
        fetchWorkflows();
      } else {
        alert('Failed to delete workflow');
      }
    } catch (err) {
      alert('Error deleting workflow');
    }
  };

  const archiveWorkflow = async (workflowId: string) => {
    const token = localStorage.getItem('auth_token');
    if (!token) return;

    try {
      const response = await fetch(`http://localhost:8000/workflows/${workflowId}/archive`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });

      if (response.ok) {
        fetchWorkflows();
      } else {
        alert('Failed to archive workflow');
      }
    } catch (err) {
      alert('Error archiving workflow');
    }
  };

  const openInN8n = (workflowId?: string) => {
    if (workflowId) {
      window.open(`http://localhost:5678/workflow/${workflowId}`, '_blank');
    } else {
      alert('This workflow has not been created in n8n yet');
    }
  };

  const handleExecuteWorkflow = async (workflowId: string) => {
    try {
      setExecutingWorkflow(workflowId);
      const result = await executeWorkflow(workflowId);

      if (result.success && result.n8n_url) {
        // Open n8n workflow in new tab
        window.open(result.n8n_url, '_blank');
        alert(result.message || 'Opening workflow in n8n. Click "Test workflow" button to execute.');
      } else if (result.success) {
        alert('Workflow executed successfully!');
      } else {
        alert(`Execution failed: ${result.message}`);
      }
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Failed to execute workflow');
    } finally {
      setExecutingWorkflow(null);
    }
  };

  if (loading) {
    return (
      <div className="p-8">
        <div className="text-center">Loading workflows...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-8">
        <div className="text-red-500">{error}</div>
      </div>
    );
  }

  return (
    <div className="p-8">
      <div className="mb-6">
        <h2 className="text-2xl font-bold mb-4">My Workflows</h2>

        {/* Filter buttons */}
        <div className="flex gap-2 mb-4">
          <button
            onClick={() => setFilter('active')}
            className={`px-4 py-2 rounded ${
              filter === 'active'
                ? 'bg-blue-500 text-white'
                : 'bg-gray-200 text-black'
            }`}
          >
            Active
          </button>
          <button
            onClick={() => setFilter('draft')}
            className={`px-4 py-2 rounded ${
              filter === 'draft'
                ? 'bg-blue-500 text-white'
                : 'bg-gray-200 text-black'
            }`}
          >
            Draft
          </button>
          <button
            onClick={() => setFilter('archived')}
            className={`px-4 py-2 rounded ${
              filter === 'archived'
                ? 'bg-blue-500 text-white'
                : 'bg-gray-200 text-black'
            }`}
          >
            Archived
          </button>
          <button
            onClick={() => setFilter('')}
            className={`px-4 py-2 rounded ${
              filter === ''
                ? 'bg-blue-500 text-white'
                : 'bg-gray-200 text-black'
            }`}
          >
            All
          </button>
        </div>
      </div>

      {workflows.length === 0 ? (
        <div className="text-center text-black py-8">
          No workflows found. Process a video to create your first workflow!
        </div>
      ) : (
        <div className="grid gap-4">
          {workflows.map((workflow) => (
            <div
              key={workflow.id}
              className="border rounded-lg p-4 hover:shadow-md transition-shadow"
            >
              <div className="flex justify-between items-start mb-2">
                <div className="flex-1">
                  <h3 className="text-lg font-semibold">{workflow.name}</h3>
                  {workflow.description && (
                    <p className="text-black text-sm mt-1">
                      {workflow.description}
                    </p>
                  )}
                </div>
                <span
                  className={`px-2 py-1 text-xs rounded ${
                    workflow.status === 'active'
                      ? 'bg-green-100 text-green-700'
                      : workflow.status === 'draft'
                      ? 'bg-yellow-100 text-yellow-700'
                      : 'bg-gray-100 text-black'
                  }`}
                >
                  {workflow.status}
                </span>
              </div>

              <div className="text-sm text-black mb-3">
                <div>Steps: {workflow.steps?.length || 0}</div>
                <div>Created: {new Date(workflow.created_at).toLocaleDateString()}</div>
                {workflow.video_key && (
                  <div className="truncate">Video: {workflow.video_key.split('/').pop()}</div>
                )}
              </div>

              <div className="flex gap-2 flex-wrap">
                {workflow.n8n_workflow_id && (
                  <>
                    <button
                      onClick={() => handleExecuteWorkflow(workflow.id)}
                      disabled={executingWorkflow === workflow.id}
                      className={`px-3 py-1 rounded text-sm font-medium ${
                        executingWorkflow === workflow.id
                          ? 'bg-green-300 text-green-700 cursor-not-allowed'
                          : 'bg-green-500 text-white hover:bg-green-600'
                      }`}
                    >
                      {executingWorkflow === workflow.id ? 'Running...' : 'Run Workflow'}
                    </button>
                    <button
                      onClick={() => openInN8n(workflow.n8n_workflow_id)}
                      className="px-3 py-1 bg-blue-500 text-white rounded text-sm hover:bg-blue-600"
                    >
                      Open in n8n
                    </button>
                  </>
                )}
                {workflow.status === 'active' && (
                  <button
                    onClick={() => setEditingWorkflow(workflow)}
                    className="px-3 py-1 bg-purple-500 text-white rounded text-sm hover:bg-purple-600"
                  >
                    ✏️ Edit
                  </button>
                )}
                <button
                  onClick={() => router.push(`/workflows/${workflow.id}`)}
                  className="px-3 py-1 bg-gray-500 text-white rounded text-sm hover:bg-gray-600"
                >
                  View Details
                </button>
                {workflow.status !== 'archived' && (
                  <button
                    onClick={() => archiveWorkflow(workflow.id)}
                    className="px-3 py-1 bg-yellow-500 text-white rounded text-sm hover:bg-yellow-600"
                  >
                    Archive
                  </button>
                )}
                <button
                  onClick={() => deleteWorkflow(workflow.id)}
                  className="px-3 py-1 bg-red-500 text-white rounded text-sm hover:bg-red-600"
                >
                  Delete
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Edit Modal */}
      {editingWorkflow && (
        <WorkflowEditChatModal
          workflowId={editingWorkflow.id}
          workflowName={editingWorkflow.name}
          onClose={() => setEditingWorkflow(null)}
          onWorkflowUpdated={() => {
            fetchWorkflows();
            setEditingWorkflow(null);
          }}
        />
      )}
    </div>
  );
}
