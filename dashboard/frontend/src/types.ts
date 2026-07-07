export interface VideoEntry {
  key: string;
  filename: string;
  pipeline_version: string;
  video_id: string;
  last_modified: string;
  size_bytes: number;
}

export interface DviSegment {
  start: number;
  end: number;
  duration: number;
  dvi_text: string;
}

export interface SegmentSummaryDetail {
  index: number;
  start_time: number;
  silence_duration: number;
  dvi_text: string;
  audio_duration: number | null;
  duration_check: "PASS" | "FAIL";
}

export interface ProcessingSummary {
  video_id: string;
  pipeline_version: string;
  summary: {
    total_silence_segments: number;
    segments_passed: number;
    segments_failed: number;
    total_silence_duration: number;
  };
  segments: SegmentSummaryDetail[];
}

export interface AppState {
  videos: VideoEntry[];
  selectedVideo: VideoEntry | null;
  videoUrl: string | null;
  segments: DviSegment[];
  summary: ProcessingSummary | null;
  currentTime: number;
  loading: {
    videos: boolean;
    videoUrl: boolean;
    segments: boolean;
    summary: boolean;
  };
  errors: {
    videos: string | null;
    videoUrl: string | null;
    segments: string | null;
  };
}

export interface InputVideo {
  video_id: string;
  key: string;
  size_mb: number;
  last_modified: string;
}

export interface ExecutionStep {
  name: string;
  status: "pending" | "running" | "succeeded" | "failed";
  entered_at: string | null;
  exited_at: string | null;
}

export interface ExecutionStatus {
  execution_arn: string;
  status: "RUNNING" | "SUCCEEDED" | "FAILED" | "TIMED_OUT" | "ABORTED";
  start_date: string;
  stop_date: string | null;
  steps: ExecutionStep[];
  error: string | null;
  cause: string | null;
}

export interface ExecutionListItem {
  execution_arn: string;
  name: string;
  pipeline_version: string;
  status: string;
  start_time: string;
}

export interface ServiceCostItem {
  service: string;
  description: string;
  usage: string;
  cost_usd: number;
}

export interface CostReport {
  execution_arn: string;
  state_machine: string;
  status: string;
  start_time: string;
  end_time: string;
  duration_seconds: number;
  cost_breakdown: ServiceCostItem[];
  total_cost_usd: number;
}
