'use client';

import { useEffect, useState } from 'react';
import WorkflowQuestionsModal from './WorkflowQuestionsModal';

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
  const [showQuestionsModal, setShowQuestionsModal] = useState(false);
  const [workflowQuestions, setWorkflowQuestions] = useState<any>(null);
  const [analyzingWorkflow, setAnalyzingWorkflow] = useState<string | null>(null);

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

  const handleCompleteWorkflow = async (workflow: Workflow) => {
    // Analyze the workflow to get questions
    setSelectedWorkflow(workflow);
    setAnalyzingWorkflow(workflow.id);

    try {
      const token = localStorage.getItem('auth_token');
      if (!token) {
        throw new Error('Please log in');
      }

      console.log('Analyzing workflow:', workflow.id);

      // Call the backend to re-analyze and get questions
      const response = await fetch('http://localhost:8000/analyze-workflow', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          workflow_id: workflow.id
        })
      });

      if (!response.ok) {
        const errorText = await response.text();
        console.error('Analysis failed:', errorText);
        throw new Error(`Failed to analyze workflow: ${errorText}`);
      }

      const data = await response.json();
      console.log('Analysis result:', data);

      if (data.questions && data.questions.length > 0) {
        setWorkflowQuestions(data.questions);
        setShowQuestionsModal(true);
      } else {
        alert('No additional information needed for this workflow');
      }
    } catch (err) {
      console.error('Error analyzing workflow:', err);
      alert(err instanceof Error ? err.message : 'Failed to analyze workflow');
    } finally {
      setAnalyzingWorkflow(null);
    }
  };

  const handleQuestionsComplete = () => {
    setShowQuestionsModal(false);
    setWorkflowQuestions(null);
    setSelectedWorkflow(null);
    // Refresh to remove from pending list
    fetchPendingWorkflows();
    // Also reload the page to update the active workflows list
    setTimeout(() => {
      window.location.reload();
    }, 500);
  };

  const handleQuestionsCancel = () => {
    setShowQuestionsModal(false);
    setWorkflowQuestions(null);
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

  if (loading) {
    return null; // Don't show anything while loading
  }

  if (error || pendingWorkflows.length === 0) {
    return null; // Don't show section if no pending workflows
  }

  return (
    <div className="p-8">
      <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-6">
        <h2 className="text-xl font-bold mb-2 text-yellow-800">
          ⚠️ Workflows Pending Your Input
        </h2>
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
                  <h3 className="font-semibold text-gray-800">{workflow.name}</h3>
                  {workflow.description && (
                    <p className="text-sm text-gray-600 mt-1">{workflow.description}</p>
                  )}
                  <p className="text-xs text-gray-500 mt-1">
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
                  disabled={analyzingWorkflow === workflow.id}
                  className={`px-4 py-2 bg-blue-500 text-white rounded text-sm hover:bg-blue-600 font-medium ${
                    analyzingWorkflow === workflow.id ? 'opacity-50 cursor-not-allowed' : ''
                  }`}
                >
                  {analyzingWorkflow === workflow.id ? 'Analyzing...' : 'Provide Missing Info'}
                </button>
                <button
                  onClick={() => deleteWorkflow(workflow.id)}
                  disabled={analyzingWorkflow === workflow.id}
                  className="px-4 py-2 bg-red-500 text-white rounded text-sm hover:bg-red-600 disabled:opacity-50"
                >
                  Delete
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>

      {showQuestionsModal && workflowQuestions && selectedWorkflow && (
        <WorkflowQuestionsModal
          questions={workflowQuestions}
          workflowDraftId={selectedWorkflow.id}
          onComplete={handleQuestionsComplete}
          onCancel={handleQuestionsCancel}
        />
      )}
    </div>
  );
}
