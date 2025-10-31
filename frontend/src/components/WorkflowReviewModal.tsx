'use client';

import { useState } from 'react';

interface Step {
  action: string;
  service: string;
  operation: string;
  parameters?: any;
}

interface WorkflowReviewModalProps {
  steps: Step[];
  workflowName: string;
  onConfirm: (updatedSteps: Step[]) => void;
  onCancel: () => void;
}

export default function WorkflowReviewModal({
  steps,
  workflowName,
  onConfirm,
  onCancel
}: WorkflowReviewModalProps) {
  const [currentSteps, setCurrentSteps] = useState<Step[]>(steps);
  const [chatMessages, setChatMessages] = useState<Array<{role: 'user' | 'assistant', content: string}>>([
    {
      role: 'assistant',
      content: "I've analyzed your video and created this workflow. Feel free to ask me to modify it!"
    }
  ]);
  const [userMessage, setUserMessage] = useState('');
  const [isModifying, setIsModifying] = useState(false);

  const handleModifyRequest = async () => {
    if (!userMessage.trim()) return;

    // Add user message to chat
    const newMessages = [...chatMessages, { role: 'user' as const, content: userMessage }];
    setChatMessages(newMessages);
    setUserMessage('');
    setIsModifying(true);

    try {
      const token = localStorage.getItem('auth_token');
      const response = await fetch('http://localhost:8000/modify-workflow', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          current_steps: currentSteps,
          user_request: userMessage
        })
      });

      if (!response.ok) {
        throw new Error('Failed to modify workflow');
      }

      const result = await response.json();

      // Add assistant response
      setChatMessages([...newMessages, {
        role: 'assistant',
        content: result.explanation || 'I\'ve updated the workflow based on your request.'
      }]);

      // Update steps
      setCurrentSteps(result.updated_steps);
    } catch (err) {
      setChatMessages([...newMessages, {
        role: 'assistant',
        content: 'Sorry, I had trouble modifying the workflow. Please try again.'
      }]);
    } finally {
      setIsModifying(false);
    }
  };

  const getStepIcon = (service: string) => {
    const icons: Record<string, string> = {
      googleSheets: '📊',
      gmail: '📧',
      googleDrive: '📁',
      dataProcessing: '⚙️',
      default: '▶️'
    };
    return icons[service] || icons.default;
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg max-w-4xl w-full max-h-[90vh] overflow-y-auto">
        <div className="p-6">
          <h2 className="text-2xl font-bold mb-2">Review Your Workflow</h2>
          <p className="text-black mb-6">
            Here's what I'll do based on your video. You can modify it before proceeding.
          </p>

          {/* Workflow Steps Display */}
          <div className="mb-6 bg-blue-50 border border-blue-200 rounded-lg p-4">
            <h3 className="font-semibold text-blue-900 mb-3 flex items-center gap-2">
              <span>📋</span>
              <span>Workflow: {workflowName}</span>
            </h3>
            <div className="space-y-3">
              {currentSteps.map((step, idx) => (
                <div key={idx} className="flex gap-3 items-start bg-white p-3 rounded-md border border-blue-100">
                  <div className="flex-shrink-0 w-8 h-8 bg-blue-500 text-white rounded-full flex items-center justify-center font-bold text-sm">
                    {idx + 1}
                  </div>
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-xl">{getStepIcon(step.service)}</span>
                      <span className="font-semibold text-black">{step.action}</span>
                    </div>
                    <div className="text-xs text-black">
                      Service: {step.service} → {step.operation}
                    </div>
                    {step.parameters && Object.keys(step.parameters).length > 0 && (
                      <div className="text-xs text-black mt-1 bg-gray-50 p-2 rounded">
                        Parameters: {Object.entries(step.parameters).map(([key, value]) =>
                          `${key}: ${JSON.stringify(value)}`
                        ).join(', ')}
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Chat Interface */}
          <div className="mb-6 border border-gray-300 rounded-lg">
            <div className="bg-gray-100 p-3 border-b border-gray-300">
              <h3 className="font-semibold text-black flex items-center gap-2">
                <span>💬</span>
                <span>Refine Your Workflow</span>
              </h3>
              <p className="text-xs text-black mt-1">
                Ask me to add, remove, or modify steps. Examples: "Add a step to filter emails by domain", "Send individual emails instead of one draft"
              </p>
            </div>

            {/* Chat Messages */}
            <div className="p-4 space-y-3 max-h-60 overflow-y-auto bg-white">
              {chatMessages.map((msg, idx) => (
                <div key={idx} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                  <div className={`max-w-[80%] p-3 rounded-lg ${
                    msg.role === 'user'
                      ? 'bg-blue-500 text-white'
                      : 'bg-gray-100 text-black'
                  }`}>
                    <p className="text-sm">{msg.content}</p>
                  </div>
                </div>
              ))}
              {isModifying && (
                <div className="flex justify-start">
                  <div className="bg-gray-100 text-black p-3 rounded-lg">
                    <p className="text-sm">Thinking...</p>
                  </div>
                </div>
              )}
            </div>

            {/* Chat Input */}
            <div className="p-3 border-t border-gray-300 bg-gray-50">
              <div className="flex gap-2">
                <input
                  type="text"
                  value={userMessage}
                  onChange={(e) => setUserMessage(e.target.value)}
                  onKeyPress={(e) => e.key === 'Enter' && !isModifying && handleModifyRequest()}
                  placeholder="Ask me to modify the workflow..."
                  className="flex-1 px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 text-black"
                  disabled={isModifying}
                />
                <button
                  onClick={handleModifyRequest}
                  disabled={isModifying || !userMessage.trim()}
                  className="px-4 py-2 bg-blue-500 text-white rounded-md hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {isModifying ? '...' : 'Send'}
                </button>
              </div>
            </div>
          </div>

          {/* Action Buttons */}
          <div className="flex gap-3 justify-end">
            <button
              onClick={onCancel}
              className="px-6 py-2 border border-gray-300 rounded-md text-black hover:bg-gray-50"
            >
              Cancel
            </button>
            <button
              onClick={() => onConfirm(currentSteps)}
              className="px-6 py-2 bg-green-500 text-white rounded-md hover:bg-green-600 font-medium"
            >
              ✓ Looks Good! Continue
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
