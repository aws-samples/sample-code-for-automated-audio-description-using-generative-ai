import { useRef, useEffect, useMemo, useState } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import type { DviSegment, SegmentSummaryDetail } from "../types";
import SegmentCard from "./SegmentCard";
import LoadingIndicator from "./LoadingIndicator";
import { Button } from "@/components/ui/button";

interface SegmentPanelProps {
  segments: DviSegment[];
  currentTime: number;
  onSeek: (time: number) => void;
  loading: boolean;
  error: string | null;
  summarySegments?: SegmentSummaryDetail[];
}

// Cap how many segment cards render at once. Long videos can produce dozens of
// segments; rendering them all makes the panel grow unbounded (the page uses
// min-h-screen), which in turn balloons the player's letterbox margins. Paging
// keeps the panel a predictable height regardless of segment count.
const SEGMENTS_PER_PAGE = 8;

function SegmentPanel({
  segments,
  currentTime,
  onSeek,
  loading,
  error,
  summarySegments,
}: SegmentPanelProps) {
  const activeRef = useRef<HTMLDivElement | null>(null);
  const [page, setPage] = useState(0);

  const sortedSegments = useMemo(
    () => [...segments].sort((a, b) => a.start - b.start),
    [segments],
  );

  const activeIndex = useMemo(() => {
    for (let i = 0; i < sortedSegments.length; i++) {
      const seg = sortedSegments[i];
      if (currentTime >= seg.start && currentTime < seg.end) {
        return i;
      }
    }
    return -1;
  }, [sortedSegments, currentTime]);

  const totalPages = Math.max(
    1,
    Math.ceil(sortedSegments.length / SEGMENTS_PER_PAGE),
  );

  // Reset to the first page whenever a different video's segments load.
  useEffect(() => {
    setPage(0);
  }, [segments]);

  // Follow playback: when the active segment is on another page, jump to it so
  // the highlighted card stays visible as the video plays.
  useEffect(() => {
    if (activeIndex >= 0) {
      setPage(Math.floor(activeIndex / SEGMENTS_PER_PAGE));
    }
  }, [activeIndex]);

  // Keep the page in range if the segment count shrinks.
  useEffect(() => {
    setPage((p) => Math.min(p, totalPages - 1));
  }, [totalPages]);

  useEffect(() => {
    if (activeRef.current) {
      activeRef.current.scrollIntoView({
        behavior: "smooth",
        block: "nearest",
      });
    }
  }, [activeIndex, page]);

  if (loading) {
    return (
      <div className="flex flex-col h-full bg-[var(--surface-container-low)]">
        <LoadingIndicator message="Loading segments..." />
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col h-full bg-[var(--surface-container-low)]">
        <div className="text-[var(--error)] p-3 bg-[var(--error-bg)] border border-[var(--ghost-border-error)] rounded-[var(--radius-md)] text-sm">
          {error}
        </div>
      </div>
    );
  }

  if (sortedSegments.length === 0) {
    return (
      <div className="flex flex-col h-full bg-[var(--surface-container-low)]">
        <div className="flex items-center justify-center h-full text-[var(--on-surface-muted)] text-sm">
          No DVI segments found for this video
        </div>
      </div>
    );
  }

  const pageStart = page * SEGMENTS_PER_PAGE;
  const pageSegments = sortedSegments.slice(
    pageStart,
    pageStart + SEGMENTS_PER_PAGE,
  );
  const showPager = totalPages > 1;

  return (
    <div className="flex flex-col h-full bg-[var(--surface-container-low)]">
      <div className="flex-1 overflow-y-auto py-1">
        {pageSegments.map((segment, i) => {
          const index = pageStart + i;
          const isActive = index === activeIndex;
          const summaryDetail = summarySegments?.find(
            (s) => s.start_time === segment.start,
          );
          return (
            <div
              key={`${segment.start}-${segment.end}`}
              ref={isActive ? activeRef : null}
            >
              <SegmentCard
                segment={segment}
                isActive={isActive}
                onClick={() => onSeek(segment.start)}
                durationCheck={summaryDetail?.duration_check}
              />
            </div>
          );
        })}
      </div>

      {showPager && (
        <nav
          aria-label="Segment pages"
          className="flex-none flex items-center justify-between gap-2 px-3 py-2 border-t border-[var(--ghost-border)]"
        >
          <Button
            variant="outline"
            size="sm"
            onClick={() => setPage((p) => Math.max(0, p - 1))}
            disabled={page === 0}
            aria-label="Previous page of segments"
            className="border-[var(--ghost-border)] text-[var(--on-surface)]"
          >
            <ChevronLeft className="h-4 w-4" />
            Prev
          </Button>

          <span
            className="text-xs text-[var(--on-surface-muted)] tabular-nums"
            aria-live="polite"
          >
            Page {page + 1} of {totalPages}
            <span className="mx-1.5 opacity-50">·</span>
            {pageStart + 1}–{pageStart + pageSegments.length} of{" "}
            {sortedSegments.length}
          </span>

          <Button
            variant="outline"
            size="sm"
            onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
            disabled={page >= totalPages - 1}
            aria-label="Next page of segments"
            className="border-[var(--ghost-border)] text-[var(--on-surface)]"
          >
            Next
            <ChevronRight className="h-4 w-4" />
          </Button>
        </nav>
      )}
    </div>
  );
}

export default SegmentPanel;
