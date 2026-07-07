import { useState, useRef, useCallback } from "react";
import type { VideoEntry, DviSegment, ProcessingSummary } from "../types";
import { fetchVideoUrl, fetchSegments, fetchSummary } from "../api";
import VideoSelector from "./VideoSelector";
import VideoPlayer from "./VideoPlayer";
import SegmentPanel from "./SegmentPanel";
import SummaryBar from "./SummaryBar";

export interface VideoPlayerHandle {
  seekTo: (time: number) => void;
}

export type VideoPlayerRef = VideoPlayerHandle;

function ViewerPage() {
  // Used by handleVideoSelect and SummaryBar integration
  const [selectedVideo, setSelectedVideo] = useState<VideoEntry | null>(null);
  void selectedVideo;
  const [videoUrl, setVideoUrl] = useState<string | null>(null);
  const [segments, setSegments] = useState<DviSegment[]>([]);
  const [summary, setSummary] = useState<ProcessingSummary | null>(null);
  const [currentTime, setCurrentTime] = useState(0);
  const [loading, setLoading] = useState({
    videos: false,
    videoUrl: false,
    segments: false,
    summary: false,
  });
  const [errors, setErrors] = useState<{
    videos: string | null;
    videoUrl: string | null;
    segments: string | null;
  }>({
    videos: null,
    videoUrl: null,
    segments: null,
  });

  const videoPlayerRef = useRef<VideoPlayerHandle | null>(null);

  const handleTimeUpdate = useCallback((time: number) => {
    setCurrentTime(time);
  }, []);

  const handleSeekTo = useCallback((time: number) => {
    videoPlayerRef.current?.seekTo(time);
  }, []);

  const handleVideoSelect = useCallback(async (video: VideoEntry) => {
    setSelectedVideo(video);
    setVideoUrl(null);
    setSegments([]);
    setSummary(null);
    setCurrentTime(0);
    setErrors({ videos: null, videoUrl: null, segments: null });
    setLoading((prev) => ({
      ...prev,
      videoUrl: true,
      segments: true,
      summary: true,
    }));

    const videoUrlPromise = fetchVideoUrl(video.key)
      .then((url) => {
        setVideoUrl(url);
        setLoading((prev) => ({ ...prev, videoUrl: false }));
      })
      .catch((err: Error) => {
        setErrors((prev) => ({ ...prev, videoUrl: err.message }));
        setLoading((prev) => ({ ...prev, videoUrl: false }));
      });

    const segmentsPromise = fetchSegments(video.video_id)
      .then((segs) => {
        setSegments(segs);
        setLoading((prev) => ({ ...prev, segments: false }));
      })
      .catch((err: Error) => {
        setErrors((prev) => ({ ...prev, segments: err.message }));
        setLoading((prev) => ({ ...prev, segments: false }));
      });

    const summaryPromise = fetchSummary(video.video_id)
      .then((sum) => {
        setSummary(sum);
        setLoading((prev) => ({ ...prev, summary: false }));
      })
      .catch(() => {
        setSummary(null);
        setLoading((prev) => ({ ...prev, summary: false }));
      });

    await Promise.all([videoUrlPromise, segmentsPromise, summaryPromise]);
  }, []);

  return (
    <div className="flex flex-col flex-1 gap-4 p-4">
      <div className="flex-none">
        <VideoSelector onSelect={handleVideoSelect} />
      </div>

      {summary && (
        <div className="flex-none">
          <SummaryBar summary={summary} />
        </div>
      )}

      <div className="flex flex-col md:flex-row flex-1 gap-4 min-h-0">
        <div className="flex-[1_1_60%] min-h-0">
          <VideoPlayer
            ref={videoPlayerRef}
            url={videoUrl}
            onTimeUpdate={handleTimeUpdate}
            error={errors.videoUrl}
            loading={loading.videoUrl}
          />
        </div>

        <div
          className="flex-[1_1_40%] min-h-0"
          role="region"
          aria-label="Segment panel"
        >
          <SegmentPanel
            segments={segments}
            currentTime={currentTime}
            onSeek={handleSeekTo}
            loading={loading.segments}
            error={errors.segments}
            summarySegments={summary?.segments}
          />
        </div>
      </div>
    </div>
  );
}

export default ViewerPage;
