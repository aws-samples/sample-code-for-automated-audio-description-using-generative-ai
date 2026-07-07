import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

interface StepCardProps {
  name: string;
  status: "pending" | "running" | "succeeded" | "failed";
}

const dotColor: Record<StepCardProps["status"], string> = {
  pending: "bg-[var(--on-surface-muted)]",
  running: "bg-[var(--primary)] animate-[step-pulse_1.2s_ease-in-out_infinite]",
  succeeded: "bg-[var(--success)]",
  failed: "bg-[var(--error)]",
};

const badgeClass: Record<StepCardProps["status"], string> = {
  pending:
    "text-[var(--on-surface-muted)] bg-[var(--surface-container-lowest)] border-transparent",
  running: "text-[var(--primary)] bg-[rgba(0,229,255,0.12)] border-transparent",
  succeeded: "text-[var(--success)] bg-[var(--success-bg)] border-transparent",
  failed: "text-[var(--error)] bg-[var(--error-bg)] border-transparent",
};

function StepCard({ name, status }: StepCardProps) {
  return (
    <Card
      role="listitem"
      className="flex items-center gap-3 px-3 py-2.5 rounded-[var(--radius-md)] bg-[var(--surface-container-high)] shadow-none border-none mb-2"
    >
      <span
        className={cn("rounded-full w-2.5 h-2.5 shrink-0", dotColor[status])}
        aria-hidden="true"
      />
      <span className="flex-1 text-sm font-medium text-[var(--on-surface)]">
        {name}
      </span>
      <Badge
        className={cn("capitalize text-xs font-semibold", badgeClass[status])}
      >
        {status}
      </Badge>
    </Card>
  );
}

export default StepCard;
