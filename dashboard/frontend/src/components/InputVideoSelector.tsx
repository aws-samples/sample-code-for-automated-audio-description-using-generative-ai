import { useState, useEffect, useCallback } from "react";
import type { InputVideo } from "../types";
import { fetchInputVideos } from "../api";
import LoadingIndicator from "./LoadingIndicator";
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from "@/components/ui/select";
import { Button } from "@/components/ui/button";

interface InputVideoSelectorProps {
  onSelect: (video: InputVideo) => void;
}

function InputVideoSelector({ onSelect }: InputVideoSelectorProps) {
  const [videos, setVideos] = useState<InputVideo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadVideos = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchInputVideos();
      const sorted = [...data].sort((a, b) =>
        a.video_id.localeCompare(b.video_id),
      );
      setVideos(sorted);
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : "Failed to load input videos";
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
        <LoadingIndicator message="Loading input videos…" />
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
        Input Video
      </label>
      <Select
        onValueChange={(key) => {
          const selected = videos.find((v) => v.key === key);
          if (selected) onSelect(selected);
        }}
      >
        <SelectTrigger className="flex-1 min-w-[200px] bg-[var(--surface-container-lowest)] text-[var(--on-surface)] border-none focus:ring-2 focus:ring-[var(--primary-glow)]">
          <SelectValue
            placeholder={`Select an input video (${videos.length} available)`}
          />
        </SelectTrigger>
        <SelectContent>
          {videos.map((video) => (
            <SelectItem key={video.key} value={video.key}>
              {video.video_id} — {video.size_mb} MB —{" "}
              {video.last_modified.slice(0, 10)}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}

export default InputVideoSelector;
