'use client'

interface VideoUploaderProps {
  videoFile: File | null
  s3Key: string | null
  isUploading: boolean
  onUpload: () => void
}

export default function VideoUploader({ videoFile, s3Key, isUploading, onUpload }: VideoUploaderProps) {
  if (!videoFile || s3Key) return null

  return (
    <button
      onClick={onUpload}
      disabled={isUploading}
      className="px-8 py-3 bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition disabled:opacity-50 disabled:cursor-not-allowed font-medium shadow-lg text-lg"
    >
      {isUploading ? 'Uploading...' : 'Upload Video'}
    </button>
  )
}