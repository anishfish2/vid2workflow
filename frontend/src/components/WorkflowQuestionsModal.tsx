'use client';

import { useState, useEffect } from 'react';

interface Question {
  step_index: number;
  step_description: string;
  missing_fields: Array<{
    field: string;
    question: string;
    type: string;
    required: boolean;
  }>;
}

interface WorkflowQuestionsModalProps {
  questions: Question[];
  workflowDraftId: string;
  onComplete: () => void;
  onCancel: () => void;
}

export default function WorkflowQuestionsModal({
  questions,
  workflowDraftId,
  onComplete,
  onCancel
}: WorkflowQuestionsModalProps) {
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showChat, setShowChat] = useState(false);
  const [chatQuestion, setChatQuestion] = useState('');
  const [chatAnswer, setChatAnswer] = useState('');
  const [chatLoading, setChatLoading] = useState(false);
  const [sheetData, setSheetData] = useState<Record<string, any>>({});
  const [loadingSheetData, setLoadingSheetData] = useState<Record<string, boolean>>({});

  // Auto-load sheet data for existing spreadsheet IDs in questions
  useEffect(() => {
    questions.forEach(async (question) => {
      // Find if this step has a sheet_column type field
      const hasSheetColumn = question.missing_fields.some(field => field.type === 'sheet_column');

      if (hasSheetColumn) {
        // Look for existing spreadsheet_id in the question or answers
        const spreadsheetIdField = question.missing_fields.find(f => f.field === 'spreadsheet_id');
        const stepKey = `step_${question.step_index}`;
        const spreadsheetIdKey = `step_${question.step_index}_spreadsheet_id`;

        // Check if spreadsheet_id already exists (from draft workflow or user input)
        const existingSpreadsheetId = answers[spreadsheetIdKey] || spreadsheetIdField?.default;

        if (existingSpreadsheetId && !sheetData[stepKey] && !loadingSheetData[stepKey]) {
          console.log('Auto-loading sheet data for step', question.step_index, 'spreadsheet:', existingSpreadsheetId);

          setLoadingSheetData(prev => ({ ...prev, [stepKey]: true }));

          try {
            const token = localStorage.getItem('auth_token');
            const response = await fetch('http://localhost:8000/enrich-sheet-question', {
              method: 'POST',
              headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
              },
              body: JSON.stringify({ spreadsheet_id: existingSpreadsheetId })
            });

            if (response.ok) {
              const result = await response.json();
              console.log('Auto-load sheet data response:', result);
              if (result.success) {
                console.log('Setting sheet data for key:', stepKey, 'data:', result.sheet_data);
                setSheetData(prev => ({
                  ...prev,
                  [stepKey]: result.sheet_data
                }));
              } else {
                console.error('Auto-load failed:', result.error);
              }
            } else {
              console.error('Auto-load HTTP error:', response.status);
            }
          } catch (err) {
            console.error('Failed to auto-load sheet data:', err);
          } finally {
            setLoadingSheetData(prev => ({ ...prev, [stepKey]: false }));
          }
        }
      }
    });
  }, [questions]);

  const handleAnswerChange = async (stepIndex: number, field: string, value: string, fieldType?: string) => {
    const key = `step_${stepIndex}_${field}`;
    setAnswers(prev => ({
      ...prev,
      [key]: value
    }));

    // If this is a spreadsheet_id field, fetch sheet data for dependent column fields
    if (field === 'spreadsheet_id' && value.trim()) {
      const sheetKey = `step_${stepIndex}`;
      setLoadingSheetData(prev => ({ ...prev, [sheetKey]: true }));

      try {
        const token = localStorage.getItem('auth_token');
        const response = await fetch('http://localhost:8000/enrich-sheet-question', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`
          },
          body: JSON.stringify({ spreadsheet_id: value })
        });

        if (response.ok) {
          const result = await response.json();
          console.log('Manual load sheet data response:', result);
          if (result.success) {
            console.log('Setting sheet data for key:', sheetKey, 'data:', result.sheet_data);
            setSheetData(prev => ({
              ...prev,
              [sheetKey]: result.sheet_data
            }));
          } else {
            console.error('Manual load failed:', result.error);
          }
        } else {
          console.error('Manual load HTTP error:', response.status);
        }
      } catch (err) {
        console.error('Failed to fetch sheet data:', err);
      } finally {
        setLoadingSheetData(prev => ({ ...prev, [sheetKey]: false }));
      }
    }
  };

  const handleAskHelper = async () => {
    if (!chatQuestion.trim()) {
      return;
    }

    setChatLoading(true);
    setChatAnswer('');

    try {
      const token = localStorage.getItem('auth_token');
      if (!token) {
        throw new Error('Please log in');
      }

      const response = await fetch('http://localhost:8000/workflow-chat-helper', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          question: chatQuestion,
          context: { questions }
        })
      });

      if (!response.ok) {
        throw new Error('Failed to get help');
      }

      const result = await response.json();
      setChatAnswer(result.answer);
    } catch (err) {
      setChatAnswer('Sorry, I could not get an answer. Please try again.');
    } finally {
      setChatLoading(false);
    }
  };

  const handleSubmit = async () => {
    // Validate all required fields are filled
    const missingAnswers: string[] = [];
    questions.forEach(q => {
      q.missing_fields.forEach(field => {
        if (field.required) {
          const key = `step_${q.step_index}_${field.field}`;
          if (!answers[key] || answers[key].trim() === '') {
            missingAnswers.push(field.question);
          }
        }
      });
    });

    if (missingAnswers.length > 0) {
      setError(`Please answer all required questions:\n${missingAnswers.join('\n')}`);
      return;
    }

    setSubmitting(true);
    setError(null);

    try {
      const token = localStorage.getItem('auth_token');
      if (!token) {
        throw new Error('Please log in');
      }

      const response = await fetch('http://localhost:8000/complete-workflow', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          workflow_draft_id: workflowDraftId,
          user_responses: answers
        })
      });

      if (!response.ok) {
        const errorData = await response.text();
        throw new Error(`Failed to complete workflow: ${errorData}`);
      }

      const result = await response.json();

      if (result.success) {
        alert('Workflow created successfully!');
        onComplete();
      } else {
        throw new Error(result.message || 'Failed to create workflow');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to complete workflow');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg max-w-2xl w-full max-h-[90vh] overflow-y-auto">
        <div className="p-6">
          <div className="flex justify-between items-start mb-4">
            <div>
              <h2 className="text-2xl font-bold">Complete Your Workflow</h2>
              <p className="text-black mt-2">
                Please provide the following information to generate a working workflow:
              </p>
            </div>
            <button
              onClick={() => setShowChat(!showChat)}
              className="px-3 py-1 bg-purple-100 text-purple-700 rounded-md text-sm hover:bg-purple-200 flex items-center gap-1"
            >
              <span>💬</span>
              {showChat ? 'Hide Helper' : 'Need Help?'}
            </button>
          </div>

          {showChat && (
            <div className="mb-6 p-4 bg-purple-50 border border-purple-200 rounded-lg">
              <h3 className="font-semibold text-purple-900 mb-2">AI Helper</h3>
              <p className="text-sm text-purple-700 mb-3">
                Ask me anything about what to fill in these fields!
              </p>
              <div className="space-y-3">
                <div className="flex gap-2">
                  <input
                    type="text"
                    className="flex-1 px-3 py-2 border border-purple-300 rounded-md focus:outline-none focus:ring-2 focus:ring-purple-500"
                    placeholder="e.g., What's a spreadsheet ID?"
                    value={chatQuestion}
                    onChange={(e) => setChatQuestion(e.target.value)}
                    onKeyPress={(e) => e.key === 'Enter' && handleAskHelper()}
                  />
                  <button
                    onClick={handleAskHelper}
                    disabled={chatLoading || !chatQuestion.trim()}
                    className="px-4 py-2 bg-purple-500 text-black rounded-md hover:bg-purple-600 disabled:opacity-50"
                  >
                    {chatLoading ? 'Thinking...' : 'Ask'}
                  </button>
                </div>
                {chatAnswer && (
                  <div className="p-3 bg-white border border-purple-200 rounded-md text-sm">
                    {chatAnswer}
                  </div>
                )}
              </div>
            </div>
          )}

          {error && (
            <div className="mb-4 p-4 bg-red-50 border border-red-200 rounded text-red-700 whitespace-pre-wrap">
              {error}
            </div>
          )}

          <div className="space-y-6">
            {questions.map((question, qIdx) => (
              <div key={qIdx} className="border rounded-lg p-4 bg-gray-50">
                <h3 className="font-semibold text-lg mb-3">
                  Step {question.step_index + 1}: {question.step_description}
                </h3>

                <div className="space-y-4">
                  {question.missing_fields.map((field, fIdx) => {
                    const sheetKey = `step_${question.step_index}`;
                    const fieldKey = `step_${question.step_index}_${field.field}`;
                    const currentSheetData = sheetData[sheetKey];
                    const isLoadingSheet = loadingSheetData[sheetKey];

                    // Debug logging for sheet column fields
                    if (field.type === 'sheet_column') {
                      console.log('Sheet column field detected:', {
                        field: field.field,
                        question: field.question,
                        sheetKey,
                        hasSheetData: !!currentSheetData,
                        sheetData: currentSheetData,
                        isLoading: isLoadingSheet
                      });
                    }

                    // Render smart search mode selector
                    if (field.type === 'smart_search') {
                      return (
                        <div key={fIdx}>
                          <label className="block text-sm font-medium text-black mb-2">
                            {field.question}
                            {field.required && <span className="text-red-500 ml-1">*</span>}
                          </label>
                          <div className="space-y-2">
                            <button
                              type="button"
                              onClick={() => handleAnswerChange(question.step_index, field.field, 'specific_column')}
                              className={`w-full p-4 text-left border-2 rounded-md transition-all ${
                                answers[fieldKey] === 'specific_column'
                                  ? 'border-blue-500 bg-blue-50'
                                  : 'border-gray-200 hover:border-blue-300'
                              }`}
                            >
                              <div className="font-semibold text-black">📍 Pick a specific column</div>
                              <div className="text-xs text-black mt-1">
                                I know exactly which column has the data (e.g., Column C has emails)
                              </div>
                            </button>
                            <button
                              type="button"
                              onClick={() => handleAnswerChange(question.step_index, field.field, 'smart_search')}
                              className={`w-full p-4 text-left border-2 rounded-md transition-all ${
                                answers[fieldKey] === 'smart_search'
                                  ? 'border-purple-500 bg-purple-50'
                                  : 'border-gray-200 hover:border-purple-300'
                              }`}
                            >
                              <div className="font-semibold text-black">🔍 Find all matching data</div>
                              <div className="text-xs text-black mt-1">
                                Search the entire sheet for emails/phones/etc. regardless of column
                              </div>
                            </button>
                          </div>
                        </div>
                      );
                    }

                    // Render data type picker (for smart search mode)
                    if (field.type === 'data_type_picker') {
                      const searchMode = answers[`step_${question.step_index}_search_mode`];
                      if (searchMode !== 'smart_search') {
                        return null; // Only show if smart search is selected
                      }

                      const dataTypes = [
                        { value: 'email', label: '📧 Email addresses', example: 'john@example.com' },
                        { value: 'phone', label: '📱 Phone numbers', example: '555-123-4567' },
                        { value: 'url', label: '🔗 URLs/Links', example: 'https://example.com' },
                        { value: 'number', label: '🔢 Numbers', example: '123.45' },
                      ];

                      return (
                        <div key={fIdx}>
                          <label className="block text-sm font-medium text-black mb-2">
                            {field.question}
                            {field.required && <span className="text-red-500 ml-1">*</span>}
                          </label>
                          <div className="grid grid-cols-2 gap-2">
                            {dataTypes.map(dt => (
                              <button
                                key={dt.value}
                                type="button"
                                onClick={() => handleAnswerChange(question.step_index, field.field, dt.value)}
                                className={`p-3 text-left border-2 rounded-md transition-all ${
                                  answers[fieldKey] === dt.value
                                    ? 'border-purple-500 bg-purple-50'
                                    : 'border-gray-200 hover:border-purple-300'
                                }`}
                              >
                                <div className="font-semibold text-sm text-black">{dt.label}</div>
                                <div className="text-xs text-black mt-1">e.g., {dt.example}</div>
                              </button>
                            ))}
                          </div>
                        </div>
                      );
                    }

                    // Render sheet column picker
                    if (field.type === 'sheet_column' && currentSheetData) {
                      return (
                        <div key={fIdx}>
                          <label className="block text-sm font-medium text-black mb-2">
                            {field.question}
                            {field.required && <span className="text-black ml-1">*</span>}
                          </label>
                          <div className="grid grid-cols-2 gap-2 max-h-60 overflow-y-auto border border-gray-300 rounded-md p-3 bg-white">
                            {Object.entries(currentSheetData.headers || {}).map(([colLetter, colName]: [string, any]) => {
                              const sampleValues = currentSheetData.sample_data
                                ?.map((row: any) => row[colLetter])
                                .filter(Boolean)
                                .slice(0, 2);

                              return (
                                <button
                                  key={colLetter}
                                  type="button"
                                  onClick={() => handleAnswerChange(question.step_index, field.field, colLetter)}
                                  className={`p-3 text-left border-2 rounded-md transition-all ${
                                    answers[fieldKey] === colLetter
                                      ? 'border-blue-500 bg-blue-50'
                                      : 'border-gray-200 hover:border-blue-300'
                                  }`}
                                >
                                  <div className="font-semibold text-sm text-black">
                                    Column {colLetter}: {colName}
                                  </div>
                                  {sampleValues && sampleValues.length > 0 && (
                                    <div className="text-xs text-black mt-1">
                                      Examples: {sampleValues.join(', ')}
                                    </div>
                                  )}
                                </button>
                              );
                            })}
                          </div>
                          {answers[fieldKey] && (
                            <p className="text-sm text-green-600 mt-2 font-medium">
                              ✓ Selected: Column {answers[fieldKey]}
                            </p>
                          )}
                        </div>
                      );
                    }

                    // Render regular input for other field types
                    return (
                      <div key={fIdx}>
                        <label className="block text-sm font-medium text-black mb-1">
                          {field.question}
                          {field.required && <span className="text-red-500 ml-1">*</span>}
                        </label>
                        <input
                          type={field.type === 'number' ? 'number' : 'text'}
                          className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 text-black"
                          placeholder={field.default || `Enter ${field.field}`}
                          value={answers[fieldKey] || field.default || ''}
                          onChange={(e) => handleAnswerChange(question.step_index, field.field, e.target.value, field.type)}
                          required={field.required}
                          disabled={field.type === 'sheet_column' && isLoadingSheet}
                        />
                        {field.type === 'sheet_column' && !currentSheetData && answers[`step_${question.step_index}_spreadsheet_id`] && (
                          <p className="text-xs text-blue-600 mt-1">
                            {isLoadingSheet ? 'Loading sheet data...' : 'Sheet data loaded! Select a column above.'}
                          </p>
                        )}
                        {field.type === 'sheet_column' && !answers[`step_${question.step_index}_spreadsheet_id`] && (
                          <p className="text-xs text-orange-600 mt-1">
                            Please enter the spreadsheet ID first
                          </p>
                        )}
                        <p className="text-xs text-black mt-1 font-medium">
                          Field: {field.field}
                        </p>
                      </div>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>

          <div className="mt-6 flex gap-3 justify-end">
            <button
              onClick={onCancel}
              disabled={submitting}
              className="px-4 py-2 border border-gray-300 rounded-md text-black hover:bg-gray-50 disabled:opacity-50"
            >
              Cancel
            </button>
            <button
              onClick={handleSubmit}
              disabled={submitting}
              className="px-4 py-2 bg-blue-500 text-white rounded-md hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {submitting ? 'Creating Workflow...' : 'Create Workflow'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
