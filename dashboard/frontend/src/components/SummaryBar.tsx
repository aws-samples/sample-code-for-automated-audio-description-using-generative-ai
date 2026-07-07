import type { ProcessingSummary } from "../types";

interface SummaryBarProps {
  summary: ProcessingSummary | null;
}

function SummaryBar({ summary }: SummaryBarProps) {
  if (!summary) return null;

  const { pipeline_version } = summary;
  const {
    total_silence_segments,
    segments_passed,
    segments_failed,
    total_silence_duration,
  } = summary.summary;

  return (
    <div
      className="flex items-center gap-6"
      role="region"
      aria-label="Processing summary"
    >
      <div className="flex items-center gap-1.5 text-[13px]">
        <span className="text-[var(--on-surface-muted)] font-medium">
          Pipeline
        </span>
        <span className="text-[var(--on-surface)] font-semibold">
          {pipeline_version}
        </span>
      </div>
      <div className="flex items-center gap-1.5 text-[13px]">
        <span className="text-[var(--on-surface-muted)] font-medium">
          Segments
        </span>
        <span className="text-[var(--on-surface)] font-semibold">
          {total_silence_segments}
        </span>
      </div>
      <div className="flex items-center gap-1.5 text-[13px]">
        <span className="text-[var(--on-surface-muted)] font-medium">
          Passed
        </span>
        <span className="text-[var(--success)] font-semibold">
          {segments_passed}
        </span>
      </div>
      <div className="flex items-center gap-1.5 text-[13px]">
        <span className="text-[var(--on-surface-muted)] font-medium">
          Failed
        </span>
        <span className="text-[var(--error)] font-semibold">
          {segments_failed}
        </span>
      </div>
      <div className="flex items-center gap-1.5 text-[13px]">
        <span className="text-[var(--on-surface-muted)] font-medium">
          Silence
        </span>
        <span className="text-[var(--on-surface)] font-semibold">
          {total_silence_duration.toFixed(1)}s
        </span>
      </div>
    </div>
  );
}

export default SummaryBar;
