import type { DviSegment } from "../types";
import { formatTimeShort } from "../utils/formatTime";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

interface SegmentCardProps {
  segment: DviSegment;
  isActive: boolean;
  onClick: () => void;
  durationCheck?: "PASS" | "FAIL";
}

function SegmentCard({
  segment,
  isActive,
  onClick,
  durationCheck,
}: SegmentCardProps) {
  return (
    <Card
      className={cn(
        "p-0 mb-2 cursor-pointer transition-[background,box-shadow] duration-150 bg-[var(--surface-container-high)] hover:bg-[var(--surface-container-highest)] border-0",
        isActive &&
          "bg-[var(--surface-container-highest)] shadow-[0_0_0_1px_var(--primary-glow),0_0_12px_var(--primary-glow)]",
      )}
      data-active={isActive || undefined}
      onClick={onClick}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onClick();
        }
      }}
      aria-label={`Segment ${formatTimeShort(segment.start)} to ${formatTimeShort(segment.end)}`}
    >
      <CardContent className="px-3 py-2.5">
        <div className="flex items-center gap-2 text-[13px] tabular-nums text-[var(--on-surface-muted)] mb-1.5">
          <span className="font-semibold text-[var(--on-surface)]">
            {formatTimeShort(segment.start)}
          </span>
          <span className="text-[var(--on-surface-muted)]">→</span>
          <span className="font-semibold text-[var(--on-surface)]">
            {formatTimeShort(segment.end)}
          </span>
          <span className="ml-auto text-xs text-[var(--on-surface-muted)] bg-[var(--surface-container-lowest)] px-1.5 py-px rounded-[3px]">
            {segment.duration.toFixed(1)}s
          </span>
          {durationCheck && (
            <Badge
              className={cn(
                "text-[11px] font-bold px-1.5 py-px rounded-[3px] uppercase tracking-[0.5px] border-0",
                durationCheck === "PASS"
                  ? "text-[var(--success)] bg-[var(--success-bg)]"
                  : "text-[var(--error)] bg-[var(--error-bg)]",
              )}
              title={
                durationCheck === "PASS"
                  ? "Narration audio fits within the silence gap"
                  : "Narration audio exceeds the silence gap duration — may overlap with dialogue"
              }
            >
              {durationCheck === "PASS" ? "Fits" : "Exceeds gap"}
            </Badge>
          )}
        </div>
        <div className="text-[13px] leading-[1.45] text-[var(--on-surface)]">
          {segment.dvi_text}
        </div>
      </CardContent>
    </Card>
  );
}

export default SegmentCard;
