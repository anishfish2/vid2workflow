'use client'

interface VideoSelectorProps {
  videoFile: File | null
  onVideoSelect: (event: React.ChangeEvent<HTMLInputElement>) => void
}

export default function VideoSelector({ videoFile, onVideoSelect }: VideoSelectorProps) {
  return (
    <div className="bg-white rounded-xl shadow-lg p-8 max-w-2xl w-full">
      <div className="flex flex-col items-center gap-4">
        <input
          type="file"
          accept="video/*"
          className="hidden"
          id="video-file-input"
          onChange={onVideoSelect}
        />

        {!videoFile ? (
          <label
            htmlFor="video-file-input"
            className="cursor-pointer flex flex-col items-center text-black hover:text-blue-600 transition p-8 border-2 border-dashed border-gray-300 rounded-lg hover:border-blue-400 w-full"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              width="48"
              height="48"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              className="feather feather-video mb-3"
            >
              <path d="M23 7l-7 5 7 5V7z"></path>
              <rect x="1" y="5" width="15" height="14" rx="2" ry="2"></rect>
            </svg>
            <span className="font-medium text-lg">Select a video to process</span>
            <span className="text-sm text-black mt-1">Click or drag to upload</span>
          </label>
        ) : (
          <div className="text-center">
            <p className="text-lg font-medium text-black">Selected:</p>
            <p className="text-sm text-black">{videoFile.name}</p>
            <label
              htmlFor="video-file-input"
              className="text-sm text-blue-500 hover:text-blue-600 cursor-pointer mt-2 inline-block"
            >
              Change video
            </label>
          </div>
        )}
      </div>
    </div>
  )
}