"""Extract silence segment video clips with context padding for AI analysis.

Extracts clips centered on each silence gap with configurable padding before
and after to provide visual narrative context to the video understanding model.
Requires FFmpeg layer.
"""
import json
import os
import re
import subprocess

import boto3

s3 = boto3.client("s3")
FFMPEG_PATH = "/opt/bin/ffmpeg"

VIDEO_ID_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_\-]{0,127}$")

# Pegasus video model requires minimum 4 seconds
MIN_PEGASUS_DURATION = 4.0

# Context padding around silence gaps (seconds).
# Provides narrative context so the model understands what's happening.
CONTEXT_PAD_BEFORE = float(os.environ.get("CONTEXT_PAD_BEFORE", "5.0"))
CONTEXT_PAD_AFTER = float(os.environ.get("CONTEXT_PAD_AFTER", "2.0"))


def get_video_duration(video_path):
    """Get video duration using ffmpeg."""
    cmd = [FFMPEG_PATH, "-i", video_path, "-f", "null", "-"]
    # Safe: constant binary (FFMPEG_PATH), list-form args with shell=False (no shell
    # interpretation); video_path is local_video derived from a VIDEO_ID_PATTERN-validated video_id.
    result = subprocess.run(cmd, capture_output=True, text=True)  # nosec B603  # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit
    for line in result.stderr.split("\n"):
        if "Duration:" in line:
            time_str = line.split("Duration:")[1].split(",")[0].strip()
            parts = time_str.split(":")
            return float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
    raise ValueError("Could not determine video duration")


def lambda_handler(event, context):
    video_id = event["video_id"]
    bucket = event["bucket"]

    if not VIDEO_ID_PATTERN.match(video_id):
        raise ValueError(f"Invalid video_id format: {video_id!r}")

    video_key = f"input/{video_id}.mp4"
    local_video = f"/tmp/{video_id}.mp4"
    s3.download_file(bucket, video_key, local_video)

    video_duration = get_video_duration(local_video)

    silence_key = f"transcribe/{video_id}/silences.json"
    silence_obj = s3.get_object(Bucket=bucket, Key=silence_key)
    silences = json.loads(silence_obj["Body"].read())["silences"]

    extracted_segments = []

    for idx, silence in enumerate(silences):
        start = silence["start"]
        end = silence["end"]
        duration = silence["duration"]

        # Add context padding around the silence gap
        extract_start = max(0, start - CONTEXT_PAD_BEFORE)
        extract_end = min(video_duration, end + CONTEXT_PAD_AFTER)
        extract_duration = extract_end - extract_start

        # Ensure minimum duration for Pegasus
        if extract_duration < MIN_PEGASUS_DURATION:
            deficit = MIN_PEGASUS_DURATION - extract_duration
            extend_before = min(deficit / 2, extract_start)
            extend_after = deficit - extend_before
            extract_start = extract_start - extend_before
            extract_end = min(video_duration, extract_end + extend_after)
            extract_duration = extract_end - extract_start
            if extract_duration < MIN_PEGASUS_DURATION:
                extract_start = max(0, extract_end - MIN_PEGASUS_DURATION)
                extract_duration = extract_end - extract_start

        output_file = f"/tmp/silence_{idx:03d}.mp4"

        command = [
            FFMPEG_PATH,
            "-ss", str(extract_start),
            "-i", local_video,
            "-t", str(extract_duration),
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-c:a", "aac",
            "-movflags", "+faststart",
            "-y",
            output_file,
        ]
        # Safe: constant binary (FFMPEG_PATH), list-form args with shell=False (no shell
        # interpretation); local_video and output_file are derived from a VIDEO_ID_PATTERN-validated video_id.
        subprocess.run(command, check=True, capture_output=True)  # nosec B603  # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit,python.lang.security.audit.dangerous-subprocess-use-tainted-env-args

        s3_key = f"silence-segments/{video_id}/segment_{idx:03d}.mp4"
        s3.upload_file(output_file, bucket, s3_key)

        extracted_segments.append({
            "segment_index": idx,
            "s3_key": s3_key,
            "start_time": start,
            "end_time": end,
            "duration": duration,
            "extract_start": extract_start,
            "extract_duration": extract_duration,
            "context_pad_before": CONTEXT_PAD_BEFORE,
            "context_pad_after": CONTEXT_PAD_AFTER,
        })

        os.remove(output_file)

    metadata_key = f"silence-segments/{video_id}/segments-metadata.json"
    s3.put_object(
        Bucket=bucket,
        Key=metadata_key,
        Body=json.dumps({"segments": extracted_segments}, indent=2),
    )

    os.remove(local_video)

    return {
        "statusCode": 200,
        "video_id": video_id,
        "bucket": bucket,
        "segments_extracted": len(extracted_segments),
    }
