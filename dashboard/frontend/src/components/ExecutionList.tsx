import type { ExecutionListItem } from "../types";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";

interface ExecutionListProps {
  executions: ExecutionListItem[];
  selectedArn: string | null;
  onSelect: (execution: ExecutionListItem) => void;
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

function ExecutionList({
  executions,
  selectedArn,
  onSelect,
}: ExecutionListProps) {
  if (executions.length === 0) {
    return (
      <div className="flex flex-col gap-2">
        <p className="text-[var(--on-surface-muted)] text-sm py-3">
          No executions found for this video
        </p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-2">
      <label className="text-sm font-semibold text-[var(--on-surface)]">
        Pipeline Executions
      </label>
      <ul
        className="list-none m-0 p-0 flex flex-col gap-1"
        role="listbox"
        aria-label="Pipeline executions"
      >
        {executions.map((exec) => {
          const isSelected = selectedArn === exec.execution_arn;
          return (
            <li
              key={exec.execution_arn}
              role="option"
              aria-selected={isSelected}
              className={cn(
                "flex items-center gap-2 px-3 py-2.5 rounded-[var(--radius-md)] cursor-pointer text-[13px] transition-colors",
                "bg-[var(--surface-container-high)] hover:bg-[var(--surface-container-highest)]",
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--primary-glow)]",
                isSelected &&
                  "bg-[var(--surface-container-highest)] shadow-[inset_3px_0_0_var(--primary-glow)]",
              )}
              onClick={() => onSelect(exec)}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") onSelect(exec);
              }}
              tabIndex={0}
            >
              <span className="flex-1 font-medium text-[var(--on-surface)] break-all leading-tight">
                {exec.name}
              </span>
              <Badge
                className={cn(
                  "text-[11px]",
                  getStatusBadgeClasses(exec.status.toLowerCase()),
                )}
              >
                {exec.status}
              </Badge>
              <span className="text-[var(--on-surface-muted)] text-xs whitespace-nowrap">
                {new Date(exec.start_time).toLocaleString()}
              </span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

export default ExecutionList;
