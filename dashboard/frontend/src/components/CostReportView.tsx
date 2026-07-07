import type { CostReport } from "../types";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import CostBreakdownTable from "./CostBreakdownTable";

interface CostReportViewProps {
  report: CostReport;
}

function formatDuration(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return `${m}m ${s}s`;
}

function getStatusBadgeClasses(status: string) {
  switch (status.toLowerCase()) {
    case "succeeded":
      return "bg-[var(--success-bg)] text-[var(--success)] border-transparent";
    case "failed":
    case "timed_out":
      return "bg-[var(--error-bg)] text-[var(--error)] border-transparent";
    case "running":
      return "bg-[rgba(0,229,255,0.12)] text-[var(--primary)] border-transparent";
    case "aborted":
      return "bg-[var(--surface-container-lowest)] text-[var(--on-surface-muted)] border-transparent";
    default:
      return "bg-[var(--surface-container-lowest)] text-[var(--on-surface-muted)] border-transparent";
  }
}

function CostReportView({ report }: CostReportViewProps) {
  const executionName = report.execution_arn.split(":").pop() || "";

  return (
    <div className="flex flex-col gap-4">
      <Card className="bg-[var(--surface-container-high)] border-none shadow-none">
        <CardHeader>
          <CardTitle className="text-base">Cost Report</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 gap-2">
            <div className="flex flex-col gap-0.5">
              <span className="text-[11px] font-semibold uppercase text-[var(--muted-foreground)]">
                Execution
              </span>
              <span className="text-[13px] text-[var(--foreground)]">
                {executionName}
              </span>
            </div>
            <div className="flex flex-col gap-0.5">
              <span className="text-[11px] font-semibold uppercase text-[var(--muted-foreground)]">
                Status
              </span>
              <div>
                <Badge
                  className={`uppercase text-xs font-bold tracking-wide ${getStatusBadgeClasses(report.status)}`}
                >
                  {report.status}
                </Badge>
              </div>
            </div>
            <div className="flex flex-col gap-0.5">
              <span className="text-[11px] font-semibold uppercase text-[var(--muted-foreground)]">
                Duration
              </span>
              <span className="text-[13px] text-[var(--foreground)]">
                {formatDuration(report.duration_seconds)}
              </span>
            </div>
            <div className="flex flex-col gap-0.5">
              <span className="text-[11px] font-semibold uppercase text-[var(--muted-foreground)]">
                Started
              </span>
              <span className="text-[13px] text-[var(--foreground)]">
                {new Date(report.start_time).toLocaleString()}
              </span>
            </div>
            <div className="flex flex-col gap-0.5">
              <span className="text-[11px] font-semibold uppercase text-[var(--muted-foreground)]">
                Ended
              </span>
              <span className="text-[13px] text-[var(--foreground)]">
                {new Date(report.end_time).toLocaleString()}
              </span>
            </div>
          </div>
        </CardContent>
      </Card>
      <CostBreakdownTable
        items={report.cost_breakdown}
        totalCost={report.total_cost_usd}
      />
    </div>
  );
}

export { formatDuration };
export default CostReportView;
