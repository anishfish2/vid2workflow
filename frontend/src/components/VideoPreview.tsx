'use client'

interface VideoPreviewProps {
  videoSrc: string | null
}

export default function VideoPreview({ videoSrc }: VideoPreviewProps) {
  if (!videoSrc) return null

  return (
    <div className="w-full max-w-2xl">
      <h3 className="text-lg font-semibold mb-2 text-gray-700">Video Preview:</h3>
      <video
        controls
        className="w-full rounded-lg shadow"
        src={videoSrc}
      >
        Your browser does not support the video tag.
      </video>
    </div>
  )
}