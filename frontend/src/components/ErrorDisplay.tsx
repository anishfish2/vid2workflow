'use client'

interface ErrorDisplayProps {
  error: string | null
}

export default function ErrorDisplay({ error }: ErrorDisplayProps) {
  if (!error) return null

  return (
    <div className="p-4 bg-red-50 border border-red-200 rounded-lg text-red-700 w-full max-w-md text-center">
      <p className="font-semibold">Error:</p>
      <p>{error}</p>
    </div>
  )
}