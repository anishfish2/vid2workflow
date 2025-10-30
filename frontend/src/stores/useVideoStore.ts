import { create } from "zustand";
import { Frame } from "@/lib/api";

type VideoState = {
  videoFile: File | null;
  setVideoFile: (file: File | null) => void;

  s3Key: string | null;
  setS3Key: (key: string | null) => void;

  isProcessing: boolean;
  setIsProcessing: (processing: boolean) => void;

  processedFrames: Frame[] | null;
  setProcessedFrames: (frames: Frame[] | null) => void;
  frameCount: number;
  setFrameCount: (count: number) => void;

  error: string | null;
  setError: (error: string | null) => void;

  reset: () => void;
};

export const useVideoStore = create<VideoState>((set) => ({
  videoFile: null,
  setVideoFile: (file) => set({ videoFile: file }),

  s3Key: null,
  setS3Key: (key) => set({ s3Key: key }),

  isProcessing: false,
  setIsProcessing: (processing) => set({ isProcessing: processing }),

  processedFrames: null,
  setProcessedFrames: (frames) => set({ processedFrames: frames }),
  frameCount: 0,
  setFrameCount: (count) => set({ frameCount: count }),

  error: null,
  setError: (error) => set({ error }),

  reset: () => set({
    videoFile: null,
    s3Key: null,
    isProcessing: false,
    processedFrames: null,
    frameCount: 0,
    error: null,
  }),
}));

