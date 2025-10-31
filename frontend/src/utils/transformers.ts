/**
 * Generic Response Transformer
 *
 * Completely technology-agnostic. LLM specifies how to map API responses
 * into options using JSONPath-like selectors.
 */

import { FieldOption } from '../types/formSchema';

/**
 * Extract value from nested object using dot notation path
 *
 * Example:
 * getValue({ data: { user: { name: "John" } } }, "data.user.name") => "John"
 */
export function getValue(obj: any, path: string): any {
  const parts = path.split('.');
  let current = obj;

  for (const part of parts) {
    if (current === null || current === undefined) {
      return undefined;
    }

    // Handle array notation like "items[0]"
    const arrayMatch = part.match(/(.+?)\[(\d+)\]/);
    if (arrayMatch) {
      current = current[arrayMatch[1]];
      if (Array.isArray(current)) {
        current = current[parseInt(arrayMatch[2])];
      }
    } else {
      current = current[part];
    }
  }

  return current;
}

/**
 * Map API response to options using LLM-specified mapping
 *
 * The LLM provides a mapping configuration that tells us:
 * 1. Where to find the array of items in the response
 * 2. How to extract value and label from each item
 * 3. (Optional) How to extract additional metadata
 *
 * Example mapping config from LLM:
 * {
 *   "items_path": "data.headers",        // Where the items array is
 *   "value_path": "key",                  // Path to value in each item (or special syntax)
 *   "label_path": "value",                // Path to label in each item
 *   "description_path": "description",    // Optional
 *   "samples_path": "samples",            // Optional
 *   "is_object_entries": true             // If items_path is an object that needs Object.entries()
 * }
 *
 * Special value_path syntax:
 * - "$key" - Use the object key (for Object.entries scenarios)
 * - "$value" - Use the object value
 * - "field.path" - Use dot notation path
 */
export function mapResponseToOptions(
  response: any,
  mapping: {
    items_path: string;
    value_path: string;
    label_path: string;
    description_path?: string;
    samples_path?: string;
    is_object_entries?: boolean;
  }
): FieldOption[] {
  try {
    // Get the items array from response
    let items = getValue(response, mapping.items_path);

    if (!items) {
      console.error('Could not find items at path:', mapping.items_path, 'in response:', response);
      return [];
    }

    // Convert object to entries if needed (e.g., { A: "Name", B: "Email" } => [["A", "Name"], ["B", "Email"]])
    if (mapping.is_object_entries && typeof items === 'object' && !Array.isArray(items)) {
      items = Object.entries(items);
    }

    if (!Array.isArray(items)) {
      console.error('Items is not an array:', items);
      return [];
    }

    // Map each item to an option
    return items.map((item, index) => {
      const option: FieldOption = {
        value: extractValue(item, mapping.value_path, index),
        label: extractValue(item, mapping.label_path, index),
      };

      if (mapping.description_path) {
        option.description = extractValue(item, mapping.description_path, index);
      }

      if (mapping.samples_path) {
        const samples = extractValue(item, mapping.samples_path, index);
        if (Array.isArray(samples)) {
          option.samples = samples;
        }
      }

      return option;
    });
  } catch (error) {
    console.error('Error mapping response to options:', error);
    return [];
  }
}

/**
 * Extract value from item using path or special syntax
 */
function extractValue(item: any, path: string, index: number): string {
  // Special syntax
  if (path === '$key') {
    // For Object.entries, item is [key, value]
    return Array.isArray(item) ? item[0] : String(item);
  }

  if (path === '$value') {
    // For Object.entries, item is [key, value]
    return Array.isArray(item) ? item[1] : String(item);
  }

  if (path === '$index') {
    return String(index);
  }

  if (path === '$item') {
    return String(item);
  }

  // Regular dot notation path
  return getValue(item, path);
}

/**
 * Resolve template parameters in trigger params
 *
 * Supports:
 * - {{field_id}} - Reference to another field's value
 * - {{USER_ID}} - Special variable for user ID
 * - {{this.value}} - Current field's value (handled by caller)
 */
export function resolveTemplateParams(
  params: Record<string, string>,
  fieldValues: Record<string, any>,
  userId: string
): Record<string, any> {
  const resolved: Record<string, any> = {};

  for (const [key, template] of Object.entries(params)) {
    if (typeof template !== 'string') {
      resolved[key] = template;
      continue;
    }

    // Check if it's a template
    const match = template.match(/^\{\{(.+?)\}\}$/);
    if (!match) {
      // Not a template, use as-is
      resolved[key] = template;
      continue;
    }

    const fieldId = match[1];

    // Handle special variables
    if (fieldId === 'USER_ID') {
      resolved[key] = userId;
    } else if (fieldId === 'this.value') {
      // This should be handled by the caller
      resolved[key] = template;
    } else {
      // Regular field reference
      resolved[key] = fieldValues[fieldId];
    }
  }

  return resolved;
}
