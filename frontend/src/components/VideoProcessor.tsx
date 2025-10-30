'use client'

interface VideoProcessorProps {
  s3Key: string | null
  isProcessing: boolean
  processedFrames: any[] | null
  onProcess: () => void
}

export default function VideoProcessor({ s3Key, isProcessing, processedFrames, onProcess }: VideoProcessorProps) {
  if (!s3Key || processedFrames) return null

  return (
    <>
      {/* Upload Success Message */}
      <div className="p-4 bg-green-50 border border-green-200 rounded-lg text-green-700">
        <p className="font-semibold">✓ Video uploaded successfully</p>
        <p className="text-sm">Ready to process</p>
      </div>

      {/* Process Button */}
      <button
        onClick={onProcess}
        disabled={isProcessing}
        className="px-8 py-3 bg-green-500 text-white rounded-lg hover:bg-green-600 transition disabled:opacity-50 disabled:cursor-not-allowed font-medium shadow-lg text-lg"
      >
        {isProcessing ? 'Processing...' : 'Process Video'}
      </button>

      {/* Processing Status */}
      {isProcessing && (
        <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg text-blue-700">
          <p className="font-semibold">Processing video...</p>
          <p>Extracting frames and generating workflow steps</p>
        </div>
      )}
    </>
  )
}