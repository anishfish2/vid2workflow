'use client';

import { useState } from 'react';
import FormRenderer from './FormRenderer';
import { QuestionStep } from '../types/formSchema';

interface WorkflowQuestionsModalProps {
  questions: QuestionStep[];
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
  const [submitting, setSubmitting] = useState(false);

  // Handle form submission
  const handleSubmit = async (answers: Record<string, any>) => {
    setSubmitting(true);

    try {
      const token = localStorage.getItem('auth_token');
      if (!token) {
        throw new Error('Please log in');
      }

      // Convert answers format for backend
      // FormRenderer returns: { field_id: value }
      // Backend expects: { step_0_field_id: value }
      const formattedAnswers: Record<string, any> = {};

      questions.forEach((question) => {
        question.fields.forEach((field) => {
          const key = `step_${question.step_index}_${field.id}`;
          formattedAnswers[key] = answers[field.id];
        });
      });

      const response = await fetch('http://localhost:8000/complete-workflow', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          workflow_draft_id: workflowDraftId,
          user_responses: formattedAnswers
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
      alert(err instanceof Error ? err.message : 'Failed to complete workflow');
    } finally {
      setSubmitting(false);
    }
  };

  // Get user ID from token
  const token = localStorage.getItem('auth_token');
  const userId = token ? JSON.parse(atob(token.split('.')[1])).user_id : '';

  return (
    <FormRenderer
      steps={questions}
      onSubmit={handleSubmit}
      onCancel={onCancel}
      userId={userId}
    />
  );
}
