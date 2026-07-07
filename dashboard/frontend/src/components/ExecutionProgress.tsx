import { Card, CardHeader, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import StepCard from "./StepCard";
import type { ExecutionStatus } from "../types";

interface ExecutionProgressProps {
  videoId: string;
  executionStatus: ExecutionStatus;
}

const statusBadgeClass: Record<ExecutionStatus["status"], string> = {
  RUNNING: "text-[var(--primary)] bg-[rgba(0,229,255,0.12)] border-transparent",
  SUCCEEDED: "text-[var(--success)] bg-[var(--success-bg)] border-transparent",
  FAILED: "text-[var(--error)] bg-[var(--error-bg)] border-transparent",
  TIMED_OUT: "text-[var(--error)] bg-[var(--error-bg)] border-transparent",
  ABORTED: "text-[var(--error)] bg-[var(--error-bg)] border-transparent",
};

function ExecutionProgress({
  videoId,
  executionStatus,
}: ExecutionProgressProps) {
  const { status, execution_arn, steps, cause } = executionStatus;

  const isTerminalError =
    status === "FAILED" || status === "TIMED_OUT" || status === "ABORTED";

  return (
    <Card className="bg-[var(--surface-container-high)] border-none shadow-none">
      <CardHeader className="gap-2 pb-0">
        <h3 className="text-base font-semibold text-[var(--on-surface)] m-0">
          Pipeline triggered for {videoId}
        </h3>
        <span className="text-xs text-[var(--on-surface-muted)] break-all">
          {execution_arn}
        </span>
        <div>
          <Badge
            className={`uppercase text-xs font-bold tracking-wide ${statusBadgeClass[status]}`}
          >
            {status}
          </Badge>
        </div>
      </CardHeader>

      <CardContent className="flex flex-col gap-4 pt-4">
        <div className="flex flex-col" role="list">
          {steps.map((step) => (
            <StepCard key={step.name} name={step.name} status={step.status} />
          ))}
        </div>

        {status === "SUCCEEDED" && (
          <div className="text-sm text-[var(--success)] bg-[var(--success-bg)] border border-[var(--ghost-border)] rounded-md px-3 py-2.5">
            Pipeline completed successfully.
          </div>
        )}

        {isTerminalError && (
          <div className="text-sm text-[var(--error)] bg-[var(--error-bg)] border border-[var(--ghost-border-error)] rounded-md px-3 py-2.5">
            Pipeline {status.toLowerCase().replace("_", " ")}.
            {cause ? ` Cause: ${cause}` : ""}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export default ExecutionProgress;
