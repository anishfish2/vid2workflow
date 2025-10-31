-- Fix steps column to be JSONB instead of TEXT to avoid truncation
ALTER TABLE workflows
ALTER COLUMN steps TYPE JSONB USING steps::JSONB;

-- Also ensure other JSON columns are JSONB
ALTER TABLE workflows
ALTER COLUMN n8n_workflow_data TYPE JSONB USING
  CASE
    WHEN n8n_workflow_data IS NULL THEN NULL
    WHEN n8n_workflow_data::text = '' THEN NULL
    ELSE n8n_workflow_data::JSONB
  END;
