
'use client';
import { useState } from 'react';

export default function WorkflowButton() {
  const [msg, setMsg] = useState<string | null>(null);

  async function handleClick() {
    setMsg('Creating workflow...');
    const res = await fetch('http://localhost:8000/create_workflow', {
      method: 'POST',
    });
    const data = await res.json();
    if (data.success) setMsg(`✅ Created workflow ID: ${data.workflow.id}`);
    else setMsg(`❌ ${data.error || 'Error'}`);
  }

  return (
    <div className="flex flex-col items-center gap-2">
      <button
        onClick={handleClick}
        className="rounded bg-black px-4 py-2 text-white"
      >
        Generate Dummy Workflow
      </button>
      {msg && <p>{msg}</p>}
    </div>
  );
}
