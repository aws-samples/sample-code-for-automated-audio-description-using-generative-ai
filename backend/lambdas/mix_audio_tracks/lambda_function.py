"""Mix DVI narration audio tracks into the original video. Requires FFmpeg layer."""
import json
import os
import re
import subprocess

import boto3

s3 = boto3.client("s3")
FFMPEG_PATH = "/opt/bin/ffmpeg"

VIDEO_ID_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_\-]{0,127}$")


def lambda_handler(event, context):
    video_id = event["video_id"]
    bucket = event["bucket"]

    if not VIDEO_ID_PATTERN.match(video_id):
        raise ValueError(f"Invalid video_id format: {video_id!r}")

    # Download original video
    video_key = f"input/{video_id}.mp4"
    local_video = f"/tmp/{video_id}.mp4"
    s3.download_file(bucket, video_key, local_video)

    # Get audio metadata
    audio_meta_key = f"audio/{video_id}/audio-metadata.json"
    audio_obj = s3.get_object(Bucket=bucket, Key=audio_meta_key)
    audio_files = json.loads(audio_obj["Body"].read())["audio_files"]

    output_path = f"/tmp/{video_id}_final.mp4"

    if not audio_files:
        # No DVI audio — just copy original
        command = [
            FFMPEG_PATH, "-i", local_video,
            "-c", "copy", "-movflags", "+faststart",
            "-y", output_path,
        ]
        # Safe: constant binary (FFMPEG_PATH), list-form args with shell=False (no shell
        # interpretation); local_video and output_path are derived from a VIDEO_ID_PATTERN-validated video_id.
        result = subprocess.run(command, capture_output=True, text=True)  # nosec B603  # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit
        if result.returncode != 0:
            raise Exception(f"FFmpeg failed: {result.stderr}")
    else:
        # Download all DVI audio files
        for audio in audio_files:
            local_path = f"/tmp/dvi_{audio['index']:03d}.mp3"
            s3.download_file(bucket, audio["audio_key"], local_path)
            audio["local_path"] = local_path

        # Build filter complex: delay each DVI audio and overlay onto original.
        # Use overlay approach instead of amix to avoid volume normalization artifacts.
        filter_parts = []

        for i, audio in enumerate(audio_files):
            delay_ms = int(audio["start"] * 1000)
            # Delay the DVI audio to the correct position and set volume
            filter_parts.append(
                f"[{i+1}:a]adelay={delay_ms}|{delay_ms},volume=1.5[a{i}]"
            )

        # Mix: use amix with normalize=0 to prevent volume normalization
        inputs = "[0:a]" + "".join([f"[a{i}]" for i in range(len(audio_files))])
        mix_part = f"{inputs}amix=inputs={len(audio_files)+1}:duration=longest:normalize=0[aout]"
        filter_complex = ";".join(filter_parts) + ";" + mix_part

        command = [FFMPEG_PATH, "-i", local_video]
        for audio in audio_files:
            command.extend(["-i", audio["local_path"]])

        command.extend([
            "-filter_complex", filter_complex,
            "-map", "0:v", "-map", "[aout]",
            "-c:v", "copy",
            "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart",
            "-y", output_path,
        ])

        # Safe: constant binary (FFMPEG_PATH), list-form args with shell=False (no shell
        # interpretation); local_video and output_path are derived from a VIDEO_ID_PATTERN-validated video_id.
        result = subprocess.run(command, capture_output=True, text=True)  # nosec B603  # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit
        if result.returncode != 0:
            raise Exception(f"FFmpeg failed: {result.stderr}")

    # Upload final video
    from datetime import datetime
    timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    final_key = f"final/{video_id}-{timestamp}.mp4"
    s3.upload_file(output_path, bucket, final_key)

    # Cleanup
    os.remove(local_video)
    os.remove(output_path)
    for audio in audio_files:
        if "local_path" in audio:
            os.remove(audio["local_path"])

    return {
        "statusCode": 200,
        "video_id": video_id,
        "bucket": bucket,
        "final_video": f"s3://{bucket}/{final_key}",
    }
