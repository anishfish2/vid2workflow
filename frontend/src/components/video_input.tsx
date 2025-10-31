'use client'
import { useState } from 'react'
import { useVideoStore } from '../stores/useVideoStore'
import { getUploadUrl, processVideo, saveVideoRecord } from '@/lib/api'
import VideoSelector from './VideoSelector'
import VideoUploader from './VideoUploader'
import VideoProcessor from './VideoProcessor'
import VideoPreview from './VideoPreview'
import FramesDisplay from './FramesDisplay'
import WorkflowSteps from './WorkflowSteps'
import ErrorDisplay from './ErrorDisplay'
import WorkflowQuestionsModal from './WorkflowQuestionsModal'
import WorkflowReviewModal from './WorkflowReviewModal'

export default function VideoInput() {
  const [videoSrc, setVideoSrc] = useState<string | null>(null)
  const [isUploading, setIsUploading] = useState(false)
  const [s3Key, setS3Key] = useState<string | null>(null)
  const [workflowSteps, setWorkflowSteps] = useState<any>(null)
  const [showReviewModal, setShowReviewModal] = useState(false)
  const [showQuestionsModal, setShowQuestionsModal] = useState(false)
  const [workflowQuestions, setWorkflowQuestions] = useState<any>(null)
  const [workflowDraftId, setWorkflowDraftId] = useState<string | null>(null)
  const [workflowName, setWorkflowName] = useState<string>('')

  const {
    videoFile,
    setVideoFile,
    isProcessing,
    setIsProcessing,
    processedFrames,
    setProcessedFrames,
    frameCount,
    setFrameCount,
    error,
    setError,
  } = useVideoStore()

  const handleVideoFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file) return

    console.log('Video file selected:', file.name, file.type, file.size)
    setVideoFile(file)
    const localUrl = URL.createObjectURL(file)
    setVideoSrc(localUrl)
    setError(null)
    // Reset previous results when selecting new video
    setProcessedFrames(null)
    setS3Key(null)
    setWorkflowSteps(null)
  }

  const handleUpload = async () => {
    if (!videoFile) return

    setIsUploading(true)
    setError(null)

    try {
      // Get presigned URL from backend
      const { url, key } = await getUploadUrl(videoFile.name, videoFile.type)

      // Upload directly to S3
      const uploadRes = await fetch(url, {
        method: 'PUT',
        headers: { 'Content-Type': videoFile.type },
        body: videoFile,
      })

      if (!uploadRes.ok) {
        throw new Error('Failed to upload video to S3')
      }

      setS3Key(key)
      console.log('Video uploaded successfully:', key)

      // Save video record to database
      await saveVideoRecord(key, videoFile.name, videoFile.size)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed')
    } finally {
      setIsUploading(false)
    }
  }

  const handleProcessVideo = async () => {
    if (!s3Key) {
      setError('Please upload a video first')
      return
    }

    setIsProcessing(true)
    setError(null)

    try {
      console.log('Processing video:', s3Key)
      const result = await processVideo(s3Key, 3)

      console.log('Processing result:', result)
      setProcessedFrames(result.frames)
      setFrameCount(result.frame_count)
      setWorkflowSteps(result.steps)
      setWorkflowName(`Video Workflow - ${videoFile?.name || 'Untitled'}`)

      // Always show review modal first
      setShowReviewModal(true)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Processing failed')
    } finally {
      setIsProcessing(false)
    }
  }

  const handleReviewConfirm = async (updatedSteps: any[]) => {
    setShowReviewModal(false)
    setWorkflowSteps(updatedSteps)

    // Now proceed with workflow planning using updated steps
    try {
      const token = localStorage.getItem('auth_token')

      // Start interactive planning with the confirmed steps
      const response = await fetch('http://localhost:8000/plan-workflow', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          steps: updatedSteps,
          workflow_name: workflowName,
          video_key: s3Key
        })
      })

      if (!response.ok) {
        throw new Error('Failed to plan workflow')
      }

      const result = await response.json()

      // Check if workflow needs clarification
      if (result.needs_clarification && result.questions) {
        setWorkflowQuestions(result.questions)
        setWorkflowDraftId(result.workflow_draft_id)
        setShowQuestionsModal(true)
      } else {
        // Workflow complete, reload page
        window.location.reload()
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to plan workflow')
    }
  }

  const handleReviewCancel = () => {
    setShowReviewModal(false)
    setWorkflowSteps(null)
  }

  const handleQuestionsComplete = () => {
    setShowQuestionsModal(false)
    setWorkflowQuestions(null)
    setWorkflowDraftId(null)
    // Refresh the page or workflow list
    window.location.reload()
  }

  const handleQuestionsCancel = () => {
    setShowQuestionsModal(false)
  }

  return (
    <div className="min-h-screen flex flex-col items-center justify-center p-4 space-y-6 bg-gray-50">
      <VideoSelector
        videoFile={videoFile}
        onVideoSelect={handleVideoFileChange}
      />

      <VideoUploader
        videoFile={videoFile}
        s3Key={s3Key}
        isUploading={isUploading}
        onUpload={handleUpload}
      />

      <VideoProcessor
        s3Key={s3Key}
        isProcessing={isProcessing}
        processedFrames={processedFrames}
        onProcess={handleProcessVideo}
      />

      <VideoPreview videoSrc={videoSrc} />

      <ErrorDisplay error={error} />

      <FramesDisplay
        frames={processedFrames}
        frameCount={frameCount}
      />

      <WorkflowSteps steps={workflowSteps} />

      {showReviewModal && workflowSteps && (
        <WorkflowReviewModal
          steps={workflowSteps}
          workflowName={workflowName}
          onConfirm={handleReviewConfirm}
          onCancel={handleReviewCancel}
        />
      )}

      {showQuestionsModal && workflowQuestions && workflowDraftId && (
        <WorkflowQuestionsModal
          questions={workflowQuestions}
          workflowDraftId={workflowDraftId}
          onComplete={handleQuestionsComplete}
          onCancel={handleQuestionsCancel}
        />
      )}
    </div>
  )
}
