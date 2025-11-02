'use client';

import { useEffect, useState } from 'react';
import WorkflowChatModal from './WorkflowChatModal';

interface Workflow {
  id: string;
  name: string;
  description?: string;
  status: string;
  created_at: string;
  steps: any[];
}

export default function PendingWorkflows() {
  const [pendingWorkflows, setPendingWorkflows] = useState<Workflow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedWorkflow, setSelectedWorkflow] = useState<Workflow | null>(null);
  const [showChatModal, setShowChatModal] = useState(false);

  useEffect(() => {
    fetchPendingWorkflows();
  }, []);

  const fetchPendingWorkflows = async () => {
    const token = localStorage.getItem('auth_token');

    if (!token) {
      setLoading(false);
      return;
    }

    try {
      setLoading(true);
      const response = await fetch('http://localhost:8000/workflows/?status=draft', {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });

      if (!response.ok) {
        throw new Error('Failed to fetch pending workflows');
      }

      const data = await response.json();
      setPendingWorkflows(data.workflows);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load pending workflows');
    } finally {
      setLoading(false);
    }
  };

  const handleCompleteWorkflow = (workflow: Workflow) => {
    // Open chat modal directly
    setSelectedWorkflow(workflow);
    setShowChatModal(true);
  };

  const handleChatComplete = () => {
    setShowChatModal(false);
    setSelectedWorkflow(null);
    // Refresh to remove from pending list
    fetchPendingWorkflows();
    // Also reload the page to update the active workflows list
    setTimeout(() => {
      window.location.reload();
    }, 500);
  };

  const handleChatCancel = () => {
    setShowChatModal(false);
    setSelectedWorkflow(null);
  };

  const deleteWorkflow = async (workflowId: string) => {
    if (!confirm('Are you sure you want to delete this draft workflow?')) {
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
        fetchPendingWorkflows();
      } else {
        alert('Failed to delete workflow');
      }
    } catch (err) {
      alert('Error deleting workflow');
    }
  };

  const createTestWorkflow = async () => {
    const token = localStorage.getItem('auth_token');
    if (!token) {
      alert('Please log in first');
      return;
    }

    try {
      const response = await fetch('http://localhost:8000/create-test-workflow', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });

      if (response.ok) {
        const result = await response.json();
        alert('Test workflow created! Check your pending workflows.');
        fetchPendingWorkflows();
      } else {
        alert('Failed to create test workflow');
      }
    } catch (err) {
      alert('Error creating test workflow');
    }
  };

  if (loading) {
    return null; // Don't show anything while loading
  }

  if (error || pendingWorkflows.length === 0) {
    // Still show the test workflow button even if no pending workflows
    return (
      <div className="p-8">
        <div className="bg-gray-50 border border-gray-200 rounded-lg p-6">
          <h3 className="text-lg font-semibold text-black mb-2">Developer Tools</h3>
          <p className="text-sm text-black mb-4">
            Create a test workflow without processing a video
          </p>
          <button
            onClick={createTestWorkflow}
            className="px-4 py-2 bg-purple-500 text-white rounded hover:bg-purple-600 font-medium"
          >
            Create Test Workflow
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="p-8">
      <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-6">
        <div className="flex justify-between items-center mb-2">
          <h2 className="text-xl font-bold text-yellow-800">
            ⚠️ Workflows Pending Your Input
          </h2>
          <button
            onClick={createTestWorkflow}
            className="px-3 py-1 bg-purple-500 text-white rounded text-sm hover:bg-purple-600 font-medium"
          >
            + Create Test Workflow
          </button>
        </div>
        <p className="text-sm text-yellow-700 mb-4">
          These workflows need additional information to be completed.
        </p>

        <div className="space-y-3">
          {pendingWorkflows.map((workflow) => (
            <div
              key={workflow.id}
              className="bg-white border border-yellow-300 rounded-lg p-4"
            >
              <div className="flex justify-between items-start mb-2">
                <div>
                  <h3 className="font-semibold text-black">{workflow.name}</h3>
                  {workflow.description && (
                    <p className="text-sm text-black mt-1">{workflow.description}</p>
                  )}
                  <p className="text-xs text-black mt-1">
                    Created: {new Date(workflow.created_at).toLocaleString()}
                  </p>
                </div>
                <span className="px-2 py-1 text-xs rounded bg-yellow-100 text-yellow-700">
                  Pending Input
                </span>
              </div>

              <div className="flex gap-2 mt-3">
                <button
                  onClick={() => handleCompleteWorkflow(workflow)}
                  className="px-4 py-2 bg-blue-500 text-white rounded text-sm hover:bg-blue-600 font-medium"
                >
                  Complete Workflow
                </button>
                <button
                  onClick={() => deleteWorkflow(workflow.id)}
                  className="px-4 py-2 bg-red-500 text-white rounded text-sm hover:bg-red-600"
                >
                  Delete
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>

      {showChatModal && selectedWorkflow && (
        <WorkflowChatModal
          workflowDraftId={selectedWorkflow.id}
          onComplete={handleChatComplete}
          onCancel={handleChatCancel}
        />
      )}
    </div>
  );
}
