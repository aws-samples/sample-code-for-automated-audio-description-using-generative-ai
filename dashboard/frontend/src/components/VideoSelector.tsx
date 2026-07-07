import { useState, useEffect, useCallback } from "react";
import type { VideoEntry } from "../types";
import { fetchVideos } from "../api";
import LoadingIndicator from "./LoadingIndicator";
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from "@/components/ui/select";
import { Button } from "@/components/ui/button";

interface VideoSelectorProps {
  onSelect: (video: VideoEntry) => void;
}

function VideoSelector({ onSelect }: VideoSelectorProps) {
  const [videos, setVideos] = useState<VideoEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadVideos = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchVideos();
      const sorted = [...data].sort((a, b) =>
        b.filename.localeCompare(a.filename),
      );
      setVideos(sorted);
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : "Failed to load videos";
      setError(message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadVideos();
  }, [loadVideos]);

  if (loading) {
    return (
      <div className="flex items-center gap-3 flex-wrap">
        <LoadingIndicator message="Loading videos…" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center gap-3 flex-wrap">
        <div className="text-[var(--error)] p-3 bg-[var(--error-bg)] border border-[var(--ghost-border-error)] rounded-[var(--radius-md)] text-sm flex items-center gap-2">
          {error}
          <Button
            variant="outline"
            size="sm"
            onClick={() => void loadVideos()}
            className="ml-auto text-[var(--error)] border-[var(--ghost-border-error)]"
          >
            Retry
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-3 flex-wrap">
      <label className="font-semibold text-sm text-[var(--on-surface)] whitespace-nowrap">
        Video
      </label>
      <Select
        onValueChange={(key) => {
          const selected = videos.find((v) => v.key === key);
          if (selected) onSelect(selected);
        }}
      >
        <SelectTrigger className="flex-1 min-w-[200px] bg-[var(--surface-container-lowest)] text-[var(--on-surface)] border-none focus:ring-2 focus:ring-[var(--primary-glow)]">
          <SelectValue
            placeholder={`Select a video (${videos.length} available)`}
          />
        </SelectTrigger>
        <SelectContent>
          {videos.map((video) => (
            <SelectItem key={video.key} value={video.key}>
              {video.filename} — {video.pipeline_version} — {video.video_id}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}

export default VideoSelector;
