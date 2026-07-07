import LoadingIndicator from "./LoadingIndicator";

interface PreviewPlayerProps {
  url: string | null;
  loading: boolean;
  error: string | null;
}

function PreviewPlayer({ url, loading, error }: PreviewPlayerProps) {
  if (loading) {
    return (
      <div className="flex flex-col h-full">
        <LoadingIndicator message="Loading preview…" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col h-full">
        <div className="text-[var(--error)] p-3 bg-[var(--error-bg)] border border-[var(--ghost-border-error)] rounded-[var(--radius-md)] m-auto text-sm text-center">
          {error}
        </div>
      </div>
    );
  }

  if (!url) {
    return (
      <div className="flex flex-col h-full">
        <div className="flex items-center justify-center h-full opacity-50 text-sm">
          Select a video to preview
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      <video
        src={url}
        controls
        className="w-full flex-1 min-h-0 bg-[var(--surface-container-lowest)] rounded-[var(--radius-md)]"
      />
    </div>
  );
}

export default PreviewPlayer;
