'use client';

import { useState, useEffect, useRef } from 'react';

interface Message {
  role: 'user' | 'assistant';
  content: string;
}

interface WorkflowChatModalProps {
  workflowDraftId: string;
  onComplete: () => void;
  onCancel: () => void;
}

export default function WorkflowChatModal({
  workflowDraftId,
  onComplete,
  onCancel
}: WorkflowChatModalProps) {
  const [messages, setMessages] = useState<Message[]>([
    {
      role: 'assistant',
      content: "Hi! I'll help you complete your workflow. Let me ask you a few questions to gather the information I need. Keep responding to me until I'm done."
    }
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [isComplete, setIsComplete] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const sendMessage = async () => {
    if (!input.trim() || loading) return;

    const userMessage = input.trim();
    setInput('');

    // Add user message to chat
    const newMessages: Message[] = [
      ...messages,
      { role: 'user', content: userMessage }
    ];
    setMessages(newMessages);
    setLoading(true);

    try {
      const token = localStorage.getItem('auth_token');
      if (!token) {
        throw new Error('Please log in');
      }

      // Send to backend
      const response = await fetch('http://localhost:8000/workflow-chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          workflow_draft_id: workflowDraftId,
          message: userMessage,
          conversation_history: messages.map(m => ({
            role: m.role,
            content: m.content
          }))
        })
      });

      if (!response.ok) {
        const errorData = await response.text();
        throw new Error(`Failed to send message: ${errorData}`);
      }

      const result = await response.json();

      // Add assistant response
      setMessages([
        ...newMessages,
        { role: 'assistant', content: result.message }
      ]);

      // Check if complete
      if (result.complete) {
        setIsComplete(true);
        // Auto-complete workflow
        setTimeout(() => {
          completeWorkflow();
        }, 1500);
      }

    } catch (err) {
      console.error('Error sending message:', err);
      setMessages([
        ...newMessages,
        {
          role: 'assistant',
          content: `Sorry, I encountered an error: ${err instanceof Error ? err.message : 'Unknown error'}. Please try again.`
        }
      ]);
    } finally {
      setLoading(false);
    }
  };

  const completeWorkflow = async () => {
    try {
      const token = localStorage.getItem('auth_token');
      if (!token) {
        throw new Error('Please log in');
      }

      const response = await fetch('http://localhost:8000/workflow-chat/complete', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          workflow_draft_id: workflowDraftId
        })
      });

      if (!response.ok) {
        const errorData = await response.text();
        throw new Error(`Failed to complete workflow: ${errorData}`);
      }

      const result = await response.json();

      if (result.success) {
        let message = 'Workflow created successfully!';

        if (result.n8n_workflow_url) {
          message += `\n\nView in n8n: ${result.n8n_workflow_url}`;
        }

        if (result.n8n_error) {
          message += `\n\nNote: Workflow saved to database but failed to publish to n8n: ${result.n8n_error}`;
        }

        alert(message);
        onComplete();

        // Reload page to show the new workflow
        setTimeout(() => {
          window.location.reload();
        }, 500);
      }
    } catch (err) {
      console.error('Error completing workflow:', err);
      alert(err instanceof Error ? err.message : 'Failed to complete workflow');
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4 text-black">
      <div className="bg-white rounded-lgcomplete your workflow max-w-3xl w-full h-[80vh] flex flex-col">
        {/* Header */}
        <div className="p-4 border-b flex items-center justify-between">
          <div>
            <h2 className="text-xl font-bold">Complete Your Workflow</h2>
            <p className="text-sm text-black">Chat with me to provide the information I need</p>
          </div>
          <button
            onClick={onCancel}
            className="text-black hover:text-black"
          >
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {messages.map((message, idx) => (
            <div
              key={idx}
              className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              <div
                className={`max-w-[80%] rounded-lg px-4 py-2 ${
                  message.role === 'user'
                    ? 'bg-blue-500 text-white'
                    : 'bg-gray-100 text-black'
                }`}
              >
                <p className="whitespace-pre-wrap">{message.content}</p>
              </div>
            </div>
          ))}

          {loading && (
            <div className="flex justify-start">
              <div className="bg-gray-100 rounded-lg px-4 py-2">
                <div className="flex space-x-2">
                  <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></div>
                  <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></div>
                  <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></div>
                </div>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Input */}
        {!isComplete && (
          <div className="p-4 border-t">
            <div className="flex gap-2">
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyPress={handleKeyPress}
                placeholder="Type your response..."
                disabled={loading}
                className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-100"
              />
              <button
                onClick={sendMessage}
                disabled={loading || !input.trim()}
                className="px-6 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Send
              </button>
            </div>
          </div>
        )}

        {isComplete && (
          <div className="p-4 border-t bg-green-50">
            <p className="text-green-700 text-center font-medium">
              Creating your workflow...
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
