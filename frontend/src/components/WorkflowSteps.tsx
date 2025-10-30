'use client'

interface Step {
  action: string
  parameters?: Record<string, any>
}

interface WorkflowStepsProps {
  steps: Step[] | { raw_text: string } | null
}

export default function WorkflowSteps({ steps }: WorkflowStepsProps) {
  if (!steps) return null

  return (
    <div className="w-full max-w-4xl">
      <h3 className="text-lg font-semibold mb-4 text-gray-700">
        Generated Workflow Steps:
      </h3>
      <div className="bg-gray-50 rounded-lg p-4 space-y-3">
        {Array.isArray(steps) ? (
          steps.map((step: Step, index: number) => (
            <div key={index} className="bg-white rounded p-3 shadow-sm">
              <div className="flex items-start">
                <span className="bg-blue-500 text-white rounded-full w-6 h-6 flex items-center justify-center text-sm font-bold mr-3 flex-shrink-0">
                  {index + 1}
                </span>
                <div className="flex-1">
                  <p className="font-medium text-gray-800">{step.action}</p>
                  {step.parameters && Object.keys(step.parameters).length > 0 && (
                    <div className="mt-1 text-sm text-gray-600">
                      {Object.entries(step.parameters).map(([key, value]) => (
                        <p key={key}>
                          <span className="font-medium">{key}:</span> {String(value)}
                        </p>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </div>
          ))
        ) : 'raw_text' in steps ? (
          <div className="bg-white rounded p-4 shadow-sm">
            <p className="whitespace-pre-wrap">{steps.raw_text}</p>
          </div>
        ) : (
          <div className="bg-white rounded p-4 shadow-sm">
            <p className="text-gray-500">No structured steps generated. Raw response:</p>
            <p className="whitespace-pre-wrap mt-2">{JSON.stringify(steps, null, 2)}</p>
          </div>
        )}
      </div>
    </div>
  )
}