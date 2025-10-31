/**
 * Dynamic Form Schema Types
 *
 * These types define the structure of LLM-generated forms with
 * dependencies, triggers, and enrichment capabilities.
 */

export interface Validator {
  type: 'minLength' | 'maxLength' | 'min' | 'max' | 'regex' | 'custom';
  value?: any;
  pattern?: string;
  message: string;
}

export interface ResponseMapping {
  items_path: string;           // JSONPath to the array of items (e.g., "data.headers")
  value_path: string;            // How to extract value from each item (e.g., "$key", "id", "field.name")
  label_path: string;            // How to extract label from each item (e.g., "$value", "name")
  description_path?: string;     // Optional description path
  samples_path?: string;         // Optional samples path
  is_object_entries?: boolean;   // Convert object to entries first
}

export interface Trigger {
  event: 'onChange' | 'onBlur' | 'onFocus';
  action: 'enrichField' | 'validateField' | 'callEndpoint';
  target_field?: string;
  endpoint: string;
  params: Record<string, string>;
  response_mapping?: ResponseMapping;  // LLM-specified mapping, replaces hardcoded transforms
}

export interface Enrichment {
  endpoint: string;
  params: Record<string, string>;
  response_mapping: ResponseMapping;
  load_trigger?: 'manual' | 'auto';  // Default: manual
}

export interface Condition {
  field: string;
  condition: 'equals' | 'notEquals' | 'isEmpty' | 'isNotEmpty' | 'contains';
  value?: any;
}

export interface FieldOption {
  value: string;
  label: string;
  description?: string;
  samples?: string[];
  metadata?: Record<string, any>;
}

export interface Field {
  id: string;
  question: string;
  type: 'string' | 'number' | 'boolean' | 'option_picker';
  required: boolean;
  default?: any;

  // Dependencies
  depends_on?: string[];
  disabled_until?: string[];

  // Validation
  validators?: Validator[];

  // Triggers (actions that happen when this field changes)
  triggers?: Trigger[];

  // Enrichment (how options are populated)
  enrichment?: Enrichment;

  // Predefined options (for option_picker without enrichment)
  options?: FieldOption[];

  // Conditional rendering
  show_when?: Condition;
  hide_when?: Condition;
}

export interface QuestionStep {
  step_index: number;
  step_description: string;
  fields: Field[];
  conditional_fields?: Field[];
}

export interface FormSchema {
  missing_info: QuestionStep[];
  complete: boolean;
}

// Legacy support - old field structure
export interface LegacyField {
  field: string;
  question: string;
  type: string;
  required: boolean;
  default?: any;
  depends_on?: string;
}

export interface LegacyQuestionStep {
  step_index: number;
  step_description: string;
  missing_fields: LegacyField[];
}

export interface LegacyFormSchema {
  missing_info: LegacyQuestionStep[];
  complete: boolean;
}
