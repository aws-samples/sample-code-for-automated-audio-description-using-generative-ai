import { useState, useRef } from "react";
import { uploadVideo } from "../api";

interface VideoUploadProps {
  onUploadComplete: () => void;
}

function VideoUpload({ onUploadComplete }: VideoUploadProps) {
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (!file.name.endsWith(".mp4")) {
      setError("Only MP4 files are supported.");
      return;
    }

    setError(null);
    setSuccess(null);
    setUploading(true);
    setProgress(0);

    try {
      await uploadVideo(file, setProgress);
      setSuccess(`Uploaded: ${file.name}`);
      onUploadComplete();
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Upload failed";
      setError(message);
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  return (
    <div className="flex flex-col gap-2">
      <label className="font-semibold text-sm text-[var(--on-surface)]">
        Upload Video
      </label>
      <div className="flex items-center gap-3">
        <label
          className={`inline-flex items-center gap-2 px-4 py-2 rounded-[var(--radius-md)] text-sm font-medium cursor-pointer transition-colors ${
            uploading
              ? "bg-[var(--surface-container-highest)] text-[var(--on-surface-muted)] cursor-not-allowed"
              : "bg-[var(--surface-container-high)] text-[var(--on-surface)] hover:bg-[var(--surface-container-highest)]"
          }`}
        >
          {uploading ? `Uploading... ${progress}%` : "Choose MP4 File"}
          <input
            ref={fileInputRef}
            type="file"
            accept="video/mp4,.mp4"
            onChange={handleFileChange}
            disabled={uploading}
            className="sr-only"
          />
        </label>
      </div>

      {uploading && (
        <div className="w-full h-2 bg-[var(--surface-container-highest)] rounded-full overflow-hidden">
          <div
            className="h-full bg-[var(--primary)] transition-all duration-300"
            style={{ width: `${progress}%` }}
          />
        </div>
      )}

      {error && (
        <p className="text-sm text-[var(--error)]">{error}</p>
      )}
      {success && (
        <p className="text-sm text-[var(--success)]">{success}</p>
      )}
    </div>
  );
}

export default VideoUpload;
