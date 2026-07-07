interface LoadingIndicatorProps {
  message?: string;
}

function LoadingIndicator({ message = "Loading..." }: LoadingIndicatorProps) {
  return (
    <div
      className="flex flex-col items-center justify-center gap-3 h-full min-h-[60px]"
      role="status"
      aria-label={message}
    >
      <div className="w-7 h-7 border-[3px] border-[var(--surface-container-high)] border-t-[var(--primary)] rounded-full animate-spin" />
      <span className="text-[var(--muted-foreground)] text-[13px]">
        {message}
      </span>
    </div>
  );
}

export default LoadingIndicator;
