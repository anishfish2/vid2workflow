'use client'

interface Frame {
  timestamp: number
  s3_url?: string
  base64?: string
}

interface FramesDisplayProps {
  frames: Frame[] | null
  frameCount: number
}

export default function FramesDisplay({ frames, frameCount }: FramesDisplayProps) {
  if (!frames || frames.length === 0) return null
  console.log(frames)

  return (
    <div className="w-full">
      <h3 className="text-lg font-semibold mb-4 text-black">
        Extracted Frames ({frameCount} total):
      </h3>
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
        {frames.map((frame, index) => (
          <div key={index} className="border rounded-lg p-2 shadow-sm bg-white">
            <img
              src={frame.s3_url || frame.base64}
              alt={`Frame at ${frame.timestamp}s`}
              className="w-full h-auto rounded"
            />
            <p className="text-sm text-center mt-1 text-black">
              {frame.timestamp}s
            </p>
          </div>
        ))}
      </div>
    </div>
  )
}
