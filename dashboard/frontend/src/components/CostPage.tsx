import { useState, useCallback } from "react";
import type { InputVideo, ExecutionListItem, CostReport } from "../types";
import { fetchExecutions, fetchCostReport } from "../api";
import InputVideoSelector from "./InputVideoSelector";
import ExecutionList from "./ExecutionList";
import CostReportView from "./CostReportView";
import LoadingIndicator from "./LoadingIndicator";
import { Button } from "./ui/button";

function CostPage() {
  const [executions, setExecutions] = useState<ExecutionListItem[]>([]);
  const [selectedArn, setSelectedArn] = useState<string | null>(null);
  const [costReport, setCostReport] = useState<CostReport | null>(null);
  const [loadingExecutions, setLoadingExecutions] = useState(false);
  const [loadingCost, setLoadingCost] = useState(false);
  const [executionsError, setExecutionsError] = useState<string | null>(null);
  const [costError, setCostError] = useState<string | null>(null);
  const [selectedVideo, setSelectedVideo] = useState<InputVideo | null>(null);

  const handleVideoSelect = useCallback(async (video: InputVideo) => {
    setSelectedVideo(video);
    setExecutions([]);
    setSelectedArn(null);
    setCostReport(null);
    setExecutionsError(null);
    setCostError(null);
    setLoadingExecutions(true);
    try {
      const data = await fetchExecutions(video.video_id);
      setExecutions(data);
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : "Failed to load executions";
      setExecutionsError(message);
    } finally {
      setLoadingExecutions(false);
    }
  }, []);

  const handleExecutionSelect = useCallback(
    async (execution: ExecutionListItem) => {
      setSelectedArn(execution.execution_arn);
      setCostReport(null);
      setCostError(null);
      setLoadingCost(true);
      try {
        const report = await fetchCostReport(execution.execution_arn);
        setCostReport(report);
      } catch (err: unknown) {
        const message =
          err instanceof Error ? err.message : "Failed to calculate cost";
        setCostError(message);
      } finally {
        setLoadingCost(false);
      }
    },
    [],
  );

  return (
    <div className="flex flex-1 min-h-0 flex-col md:flex-row">
      <div className="flex-none w-full md:w-[480px] bg-[var(--surface-container-low)] text-[var(--on-surface)] p-4 overflow-y-auto flex flex-col gap-4">
        <InputVideoSelector onSelect={handleVideoSelect} />

        {loadingExecutions && (
          <LoadingIndicator message="Loading executions…" />
        )}

        {executionsError && (
          <div className="text-[var(--error)] p-3 bg-[var(--error-bg)] border border-[var(--ghost-border-error)] rounded-[var(--radius-md)] text-sm flex items-center gap-2">
            {executionsError}
            <Button
              variant="outline"
              size="sm"
              onClick={() => selectedVideo && handleVideoSelect(selectedVideo)}
              className="ml-auto text-[var(--error)] border-[var(--ghost-border-error)]"
            >
              Retry
            </Button>
          </div>
        )}

        {!loadingExecutions && !executionsError && selectedVideo && (
          <ExecutionList
            executions={executions}
            selectedArn={selectedArn}
            onSelect={handleExecutionSelect}
          />
        )}
      </div>

      <div className="flex-1 bg-[var(--surface)] text-[var(--on-surface)] p-4 overflow-y-auto">
        {loadingCost && <LoadingIndicator message="Calculating cost…" />}

        {costError && (
          <div className="text-[var(--error)] p-3 bg-[var(--error-bg)] border border-[var(--ghost-border-error)] rounded-[var(--radius-md)] text-sm flex items-center gap-2">
            {costError}
            {selectedArn && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  const exec = executions.find(
                    (e) => e.execution_arn === selectedArn,
                  );
                  if (exec) handleExecutionSelect(exec);
                }}
                className="ml-auto text-[var(--error)] border-[var(--ghost-border-error)]"
              >
                Retry
              </Button>
            )}
          </div>
        )}

        {!loadingCost && !costError && costReport && (
          <CostReportView report={costReport} />
        )}

        {!loadingCost && !costError && !costReport && (
          <div className="text-[var(--on-surface-muted)] text-sm text-center py-12 px-4">
            Select a video and execution to view cost breakdown
          </div>
        )}
      </div>
    </div>
  );
}

export default CostPage;
