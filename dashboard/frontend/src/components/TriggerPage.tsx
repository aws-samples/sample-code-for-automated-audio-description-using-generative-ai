import { useState, useEffect, useRef, useCallback } from "react";
import type { InputVideo, ExecutionStatus } from "../types";
import {
  fetchInputVideoUrl,
  startExecution,
  fetchExecutionStatus,
} from "../api";
import InputVideoSelector from "./InputVideoSelector";
import PreviewPlayer from "./PreviewPlayer";
import TriggerButton from "./TriggerButton";
import ExecutionProgress from "./ExecutionProgress";
import VideoUpload from "./VideoUpload";

const TERMINAL_STATES = ["SUCCEEDED", "FAILED", "TIMED_OUT", "ABORTED"];
const POLL_INTERVAL_MS = 10_000;
const STORAGE_KEY = "dvi-active-execution";

function TriggerPage() {
  const [selectedVideo, setSelectedVideo] = useState<InputVideo | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [executionStatus, setExecutionStatus] =
    useState<ExecutionStatus | null>(null);
  const [triggerLoading, setTriggerLoading] = useState(false);
  const [triggerError, setTriggerError] = useState<string | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const [minSilenceGap, setMinSilenceGap] = useState(4);

  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const stopPolling = useCallback(() => {
    if (pollingRef.current !== null) {
      clearInterval(pollingRef.current);
      pollingRef.current = null;
    }
  }, []);

  const startPolling = useCallback(
    (arn: string) => {
      stopPolling();
      // Poll immediately, then at interval
      fetchExecutionStatus(arn)
        .then((status) => {
          setExecutionStatus(status);
          if (TERMINAL_STATES.includes(status.status)) {
            localStorage.removeItem(STORAGE_KEY);
            return;
          }
          pollingRef.current = setInterval(async () => {
            try {
              const s = await fetchExecutionStatus(arn);
              setExecutionStatus(s);
              if (TERMINAL_STATES.includes(s.status)) {
                stopPolling();
                localStorage.removeItem(STORAGE_KEY);
              }
            } catch (err) {
              console.error("Failed to fetch execution status:", err);
            }
          }, POLL_INTERVAL_MS);
        })
        .catch((err) => {
          console.error("Failed to fetch execution status:", err);
        });
    },
    [stopPolling],
  );

  // On mount, check if there's an active execution to resume
  useEffect(() => {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved) {
      try {
        const { arn, videoId } = JSON.parse(saved);
        setSelectedVideo({ video_id: videoId, key: "", size_mb: 0, last_modified: "" });
        startPolling(arn);
      } catch {
        localStorage.removeItem(STORAGE_KEY);
      }
    }
  }, [startPolling]);

  useEffect(() => {
    return () => {
      stopPolling();
    };
  }, [stopPolling]);

  const handleVideoSelect = useCallback(async (video: InputVideo) => {
    setSelectedVideo(video);
    setPreviewUrl(null);
    setPreviewError(null);
    setPreviewLoading(true);
    try {
      const url = await fetchInputVideoUrl(video.video_id);
      setPreviewUrl(url);
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : "Failed to load video preview";
      setPreviewError(message);
    } finally {
      setPreviewLoading(false);
    }
  }, []);

  const handleTrigger = useCallback(async () => {
    if (!selectedVideo) return;

    setTriggerLoading(true);
    setTriggerError(null);
    try {
      const result = await startExecution(selectedVideo.video_id, minSilenceGap);
      const initialStatus: ExecutionStatus = {
        execution_arn: result.execution_arn,
        status: "RUNNING",
        start_date: result.start_date,
        stop_date: null,
        steps: [],
        error: null,
        cause: null,
      };
      setExecutionStatus(initialStatus);
      // Persist execution to survive page refresh
      localStorage.setItem(
        STORAGE_KEY,
        JSON.stringify({ arn: result.execution_arn, videoId: selectedVideo.video_id }),
      );
      startPolling(result.execution_arn);
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : "Failed to start execution";
      setTriggerError(message);
    } finally {
      setTriggerLoading(false);
    }
  }, [selectedVideo, startPolling]);

  return (
    <div className="flex flex-1 min-h-0 flex-col md:flex-row">
      <div className="flex-[1_1_60%] bg-[var(--surface-container-lowest)] text-[var(--on-surface)] p-4 flex flex-col min-h-[400px] md:min-h-[400px] rounded-[var(--radius-lg)]">
        <PreviewPlayer
          url={previewUrl}
          loading={previewLoading}
          error={previewError}
        />
      </div>

      <div className="flex-[1_1_40%] bg-[var(--surface-container-low)] text-[var(--on-surface)] p-4 overflow-y-auto min-h-[400px] md:min-h-[400px] flex flex-col gap-4 rounded-[var(--radius-lg)]">
        <VideoUpload onUploadComplete={() => setRefreshKey((k) => k + 1)} />

        <InputVideoSelector key={refreshKey} onSelect={handleVideoSelect} />

        <div className="flex flex-col gap-1">
          <label className="font-semibold text-sm text-[var(--on-surface)]">
            Minimum Silence Gap: {minSilenceGap}s
          </label>
          <p className="text-xs text-[var(--on-surface-muted)] mb-1">
            Only silence gaps longer than this threshold will receive narration.
          </p>
          <input
            type="range"
            min={2}
            max={15}
            step={1}
            value={minSilenceGap}
            onChange={(e) => setMinSilenceGap(Number(e.target.value))}
            className="w-full accent-[var(--primary)]"
          />
          <div className="flex justify-between text-xs text-[var(--on-surface-muted)]">
            <span>2s</span>
            <span>15s</span>
          </div>
        </div>

        <div className="flex flex-col gap-3">
          <TriggerButton
            disabled={selectedVideo === null}
            loading={triggerLoading}
            onClick={handleTrigger}
          />
        </div>

        {executionStatus && selectedVideo && (
          <ExecutionProgress
            videoId={selectedVideo.video_id}
            executionStatus={executionStatus}
          />
        )}

        {triggerError && (
          <div className="text-[var(--error)] p-3 bg-[var(--error-bg)] border border-[var(--ghost-border-error)] rounded-[var(--radius-md)] text-sm">
            {triggerError}
          </div>
        )}
      </div>
    </div>
  );
}

export default TriggerPage;
