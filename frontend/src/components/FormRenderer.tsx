'use client';

import { useState, useEffect } from 'react';
import { Field, FieldOption, QuestionStep, Trigger } from '../types/formSchema';
import { mapResponseToOptions, resolveTemplateParams } from '../utils/transformers';

interface FormRendererProps {
  steps: QuestionStep[];
  onSubmit: (answers: Record<string, any>) => void;
  onCancel: () => void;
  userId: string;
}

export default function FormRenderer({
  steps,
  onSubmit,
  onCancel,
  userId
}: FormRendererProps) {
  const [fieldValues, setFieldValues] = useState<Record<string, any>>({});
  const [fieldOptions, setFieldOptions] = useState<Record<string, FieldOption[]>>({});
  const [loadingFields, setLoadingFields] = useState<Record<string, boolean>>({});
  const [errors, setErrors] = useState<Record<string, string>>({});

  // Handle field value change
  const handleFieldChange = (fieldId: string, value: any) => {
    // Update value
    setFieldValues(prev => ({ ...prev, [fieldId]: value }));

    // Clear error for this field
    setErrors(prev => {
      const newErrors = { ...prev };
      delete newErrors[fieldId];
      return newErrors;
    });
  };

  // Load options for an option_picker field
  const loadOptions = async (field: Field) => {
    if (!field.enrichment) return;

    setLoadingFields(prev => ({ ...prev, [field.id]: true }));
    setErrors(prev => {
      const newErrors = { ...prev };
      delete newErrors[field.id];
      return newErrors;
    });

    try {
      // Resolve template parameters
      const params = resolveTemplateParams(
        field.enrichment.params,
        fieldValues,
        userId
      );

      // Call the endpoint
      const token = localStorage.getItem('auth_token');
      const response = await fetch(`http://localhost:8000${field.enrichment.endpoint}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify(params)
      });

      if (!response.ok) {
        throw new Error(`API call failed: ${response.statusText}`);
      }

      const data = await response.json();

      // Map response to options using LLM-specified mapping
      const options = mapResponseToOptions(data, field.enrichment.response_mapping);

      // Set options for this field
      setFieldOptions(prev => ({ ...prev, [field.id]: options }));

    } catch (error) {
      console.error('Failed to load options:', error);
      setErrors(prev => ({
        ...prev,
        [field.id]: `Failed to load options: ${error instanceof Error ? error.message : 'Unknown error'}`
      }));
    } finally {
      setLoadingFields(prev => ({ ...prev, [field.id]: false }));
    }
  };

  // Check if field should be disabled
  const isFieldDisabled = (field: Field): boolean => {
    if (!field.disabled_until) return false;
    return field.disabled_until.some(depFieldId => {
      const value = fieldValues[depFieldId];
      return !value || (typeof value === 'string' && value.trim() === '');
    });
  };

  // Validate all fields
  const validateFields = (): boolean => {
    const newErrors: Record<string, string> = {};

    steps.forEach(step => {
      step.fields.forEach(field => {
        if (field.required) {
          const value = fieldValues[field.id];
          if (!value || (typeof value === 'string' && value.trim() === '')) {
            newErrors[field.id] = `${field.question} is required`;
          }
        }

        // Run validators
        if (field.validators && fieldValues[field.id]) {
          for (const validator of field.validators) {
            const value = fieldValues[field.id];

            switch (validator.type) {
              case 'minLength':
                if (typeof value === 'string' && value.length < validator.value) {
                  newErrors[field.id] = validator.message;
                }
                break;
              case 'maxLength':
                if (typeof value === 'string' && value.length > validator.value) {
                  newErrors[field.id] = validator.message;
                }
                break;
              case 'min':
                if (typeof value === 'number' && value < validator.value) {
                  newErrors[field.id] = validator.message;
                }
                break;
              case 'max':
                if (typeof value === 'number' && value > validator.value) {
                  newErrors[field.id] = validator.message;
                }
                break;
              case 'regex':
                if (typeof value === 'string' && validator.pattern && !new RegExp(validator.pattern).test(value)) {
                  newErrors[field.id] = validator.message;
                }
                break;
            }
          }
        }
      });
    });

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  // Handle form submission
  const handleSubmit = () => {
    if (validateFields()) {
      onSubmit(fieldValues);
    }
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg max-w-2xl w-full max-h-[90vh] overflow-y-auto">
        <div className="p-6">
          <h2 className="text-2xl font-bold mb-4">Complete Your Workflow</h2>
          <p className="text-black mb-6">
            Please provide the following information to generate a working workflow:
          </p>

          <div className="space-y-6">
            {steps.map((step, stepIdx) => (
              <div key={stepIdx} className="border rounded-lg p-4 bg-gray-50">
                <h3 className="font-semibold text-lg mb-4">
                  Step {step.step_index + 1}: {step.step_description}
                </h3>

                <div className="space-y-4">
                  {step.fields.map((field, fieldIdx) => (
                    <FieldInput
                      key={fieldIdx}
                      field={field}
                      value={fieldValues[field.id]}
                      options={fieldOptions[field.id] || field.options || []}
                      loading={loadingFields[field.id]}
                      disabled={isFieldDisabled(field)}
                      error={errors[field.id]}
                      onChange={(value) => handleFieldChange(field.id, value)}
                      onLoadOptions={() => loadOptions(field)}
                    />
                  ))}
                </div>
              </div>
            ))}
          </div>

          <div className="mt-6 flex gap-3 justify-end">
            <button
              onClick={onCancel}
              className="px-4 py-2 border border-gray-300 rounded-md text-black hover:bg-gray-50"
            >
              Cancel
            </button>
            <button
              onClick={handleSubmit}
              className="px-4 py-2 bg-blue-500 text-white rounded-md hover:bg-blue-600"
            >
              Create Workflow
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

// Field input component
interface FieldInputProps {
  field: Field;
  value: any;
  options: FieldOption[];
  loading?: boolean;
  disabled?: boolean;
  error?: string;
  onChange: (value: any) => void;
  onLoadOptions: () => void;
}

function FieldInput({ field, value, options, loading, disabled, error, onChange, onLoadOptions }: FieldInputProps) {
  const renderInput = () => {
    switch (field.type) {
      case 'string':
        return (
          <input
            type="text"
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            value={value || field.default || ''}
            onChange={(e) => onChange(e.target.value)}
            disabled={disabled}
            placeholder={field.default ? String(field.default) : undefined}
          />
        );

      case 'number':
        return (
          <input
            type="number"
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            value={value !== undefined ? value : (field.default || '')}
            onChange={(e) => onChange(parseFloat(e.target.value))}
            disabled={disabled}
            placeholder={field.default ? String(field.default) : undefined}
          />
        );

      case 'boolean':
        return (
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              className="w-4 h-4"
              checked={value !== undefined ? value : (field.default || false)}
              onChange={(e) => onChange(e.target.checked)}
              disabled={disabled}
            />
            <span className="text-sm text-black">{field.question}</span>
          </label>
        );

      case 'option_picker':
        // Check if field has enrichment (needs to load options from API)
        const hasEnrichment = field.enrichment !== undefined;
        const hasOptions = options.length > 0;

        return (
          <div className="space-y-2">
            {hasEnrichment && (
              <button
                type="button"
                onClick={onLoadOptions}
                disabled={disabled || loading}
                className="px-4 py-2 bg-blue-500 text-white rounded-md hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed text-sm"
              >
                {loading ? 'Loading...' : hasOptions ? 'Reload Options' : 'Load Options'}
              </button>
            )}

            {disabled && !hasOptions && (
              <div className="text-sm text-black">
                Please fill in required fields first, then click "Load Options"
              </div>
            )}

            {hasOptions && (
              <div className="grid grid-cols-2 gap-2 max-h-60 overflow-y-auto border border-gray-300 rounded-md p-3 bg-white">
                {options.map((option) => (
                  <button
                    key={option.value}
                    type="button"
                    onClick={() => onChange(option.value)}
                    className={`p-3 text-left border-2 rounded-md transition-all ${
                      value === option.value
                        ? 'border-blue-500 bg-blue-50'
                        : 'border-gray-200 hover:border-blue-300'
                    }`}
                  >
                    <div className="font-semibold text-sm">{option.label}</div>
                    {option.description && (
                      <div className="text-xs text-black mt-1">{option.description}</div>
                    )}
                    {option.samples && option.samples.length > 0 && (
                      <div className="text-xs text-black mt-1">
                        Examples: {option.samples.join(', ')}
                      </div>
                    )}
                  </button>
                ))}
              </div>
            )}
          </div>
        );

      default:
        return <div className="text-red-500">Unknown field type: {field.type}</div>;
    }
  };

  return (
    <div>
      {field.type !== 'boolean' && (
        <label className="block text-sm font-medium text-black mb-1">
          {field.question}
          {field.required && <span className="text-red-500 ml-1">*</span>}
        </label>
      )}

      {renderInput()}

      {error && (
        <p className="text-xs text-red-600 mt-1">{error}</p>
      )}

      {value && field.type === 'option_picker' && options.length > 0 && (
        <p className="text-xs text-green-600 mt-1">
          ✓ Selected: {options.find(o => o.value === value)?.label}
        </p>
      )}
    </div>
  );
}
