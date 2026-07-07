import { forwardRef, useImperativeHandle, useRef, useState } from "react";
import { formatTime } from "../utils/formatTime";
import type { VideoPlayerHandle } from "./ViewerPage";
import LoadingIndicator from "./LoadingIndicator";

interface VideoPlayerProps {
  url: string | null;
  onTimeUpdate: (time: number) => void;
  error: string | null;
  loading: boolean;
}

const VideoPlayer = forwardRef<VideoPlayerHandle, VideoPlayerProps>(
  ({ url, onTimeUpdate, error, loading }, ref) => {
    const videoRef = useRef<HTMLVideoElement>(null);
    const [currentTime, setCurrentTime] = useState(0);

    useImperativeHandle(ref, () => ({
      seekTo(time: number) {
        if (videoRef.current) {
          videoRef.current.currentTime = time;
        }
      },
    }));

    const handleTimeUpdate = () => {
      if (videoRef.current) {
        const t = videoRef.current.currentTime;
        setCurrentTime(t);
        onTimeUpdate(t);
      }
    };

    if (loading) {
      return (
        <div className="flex flex-col h-full">
          <LoadingIndicator message="Loading video…" />
        </div>
      );
    }

    if (error) {
      return (
        <div className="flex flex-col h-full">
          <div className="text-[var(--error)] p-3 bg-[var(--error-bg)] border border-[var(--ghost-border-error)] rounded-[var(--radius-md)] m-auto text-sm text-center">
            {error}
          </div>
        </div>
      );
    }

    if (!url) {
      return (
        <div className="flex flex-col h-full">
          <div className="flex items-center justify-center h-full opacity-50 text-sm">
            Select a video to begin
          </div>
        </div>
      );
    }

    return (
      <div className="flex flex-col h-full">
        <video
          ref={videoRef}
          src={url}
          controls
          onTimeUpdate={handleTimeUpdate}
          className="w-full flex-1 min-h-0 bg-[var(--surface-container-lowest)] rounded-[var(--radius-md)]"
        />
        <div className="mt-2 text-sm tabular-nums text-[var(--on-surface-muted)] text-center">
          {formatTime(currentTime)}
        </div>
      </div>
    );
  },
);

VideoPlayer.displayName = "VideoPlayer";

export default VideoPlayer;
