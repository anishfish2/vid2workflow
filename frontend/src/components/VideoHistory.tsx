'use client';

import { useEffect, useState } from 'react';
import { getUserVideos, processVideo } from '@/lib/api';

interface Video {
  id: string;
  s3_key: string;
  filename: string;
  file_size?: number;
  uploaded_at: string;
}

interface VideoHistoryProps {
  onSelectVideo?: (s3Key: string) => void;
}

export default function VideoHistory({ onSelectVideo }: VideoHistoryProps) {
  const [videos, setVideos] = useState<Video[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [processingVideo, setProcessingVideo] = useState<string | null>(null);

  useEffect(() => {
    fetchVideos();
  }, []);

  const fetchVideos = async () => {
    try {
      setLoading(true);
      const data = await getUserVideos();
      setVideos(data.videos);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load videos');
    } finally {
      setLoading(false);
    }
  };

  const handleProcessVideo = async (s3Key: string) => {
    try {
      setProcessingVideo(s3Key);
      setError(null);

      await processVideo(s3Key, 3);

      alert('Video processed successfully! Check the workflow list below.');

    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to process video');
    } finally {
      setProcessingVideo(null);
    }
  };

  const formatFileSize = (bytes?: number) => {
    if (!bytes) return 'Unknown';
    const mb = bytes / (1024 * 1024);
    return `${mb.toFixed(2)} MB`;
  };

  if (loading) {
    return (
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-xl font-semibold mb-4">Previously Uploaded Videos</h2>
        <div className="text-center text-black">Loading videos...</div>
      </div>
    );
  }

  if (error && videos.length === 0) {
    return (
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-xl font-semibold mb-4">Previously Uploaded Videos</h2>
        <div className="text-center text-red-500">{error}</div>
      </div>
    );
  }

  if (videos.length === 0) {
    return (
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-xl font-semibold mb-4">Previously Uploaded Videos</h2>
        <div className="text-center text-black">
          No videos uploaded yet. Upload a video above to get started.
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <h2 className="text-xl font-semibold mb-4">Previously Uploaded Videos</h2>

      {error && (
        <div className="mb-4 p-3 bg-red-50 text-red-600 rounded">
          {error}
        </div>
      )}

      <div className="space-y-3">
        {videos.map((video) => (
          <div
            key={video.id}
            className="border rounded-lg p-4 hover:shadow-md transition-shadow"
          >
            <div className="flex justify-between items-start">
              <div className="flex-1">
                <h3 className="font-semibold text-black">{video.filename}</h3>
                <div className="text-sm text-black mt-1">
                  <div>Size: {formatFileSize(video.file_size)}</div>
                  <div>Uploaded: {new Date(video.uploaded_at).toLocaleString()}</div>
                  <div className="truncate text-xs mt-1">Key: {video.s3_key}</div>
                </div>
              </div>
              <div className="flex gap-2 ml-4">
                <button
                  onClick={() => handleProcessVideo(video.s3_key)}
                  disabled={processingVideo === video.s3_key}
                  className={`px-4 py-2 rounded text-sm font-medium ${
                    processingVideo === video.s3_key
                      ? 'bg-gray-300 text-black cursor-not-allowed'
                      : 'bg-blue-500 text-white hover:bg-blue-600'
                  }`}
                >
                  {processingVideo === video.s3_key ? 'Processing...' : 'Process Video'}
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
