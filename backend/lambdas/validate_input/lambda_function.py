"""Validate input video and extract metadata before pipeline processing.

Checks:
- Video exists in S3
- File size within Lambda processing limits (< 8 GB)
- Video duration within Transcribe limits (< 8 hours)

Stores metadata for downstream steps and cost calculation.
"""
import json
import os
import re
import subprocess

import boto3

s3 = boto3.client("s3")
FFMPEG_PATH = "/opt/bin/ffmpeg"

VIDEO_ID_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_\-]{0,127}$")

# Processing limits (based on Lambda ephemeral storage and service quotas)
MAX_FILE_SIZE_BYTES = 8 * 1024 * 1024 * 1024  # 8 GB (Lambda /tmp is 10 GB, need headroom)
MAX_DURATION_SECONDS = 28800  # 8 hours (Amazon Transcribe limit)


def get_duration_from_s3(bucket, key):
    """Get video duration by streaming the header from S3 via presigned URL.
    
    FFmpeg can probe duration from a URL without downloading the entire file.
    """
    url = s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": key},
        ExpiresIn=300,
    )

    cmd = [
        FFMPEG_PATH, "-i", url,
        "-f", "null", "-t", "0", "-"
    ]
    # Safe: constant binary (FFMPEG_PATH), list-form args with shell=False (no shell
    # interpretation), and video_id is validated against VIDEO_ID_PATTERN before use.
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)  # nosec B603  # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit

    for line in result.stderr.split("\n"):
        if "Duration:" in line:
            time_str = line.split("Duration:")[1].split(",")[0].strip()
            parts = time_str.split(":")
            return float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])

    return None


def lambda_handler(event, context):
    video_id = event["video_id"]
    bucket = event["bucket"]

    if not VIDEO_ID_PATTERN.match(video_id):
        raise ValueError(f"Invalid video_id format: {video_id!r}")

    video_key = f"input/{video_id}.mp4"

    # Check file exists and get size
    try:
        head = s3.head_object(Bucket=bucket, Key=video_key)
    except Exception as e:
        error_code = getattr(e, "response", {}).get("Error", {}).get("Code", "")
        if error_code == "404" or "Not Found" in str(e):
            raise ValueError(
                f"Video not found: {video_key}. "
                "Ensure the video is uploaded to the input/ prefix."
            )
        raise

    file_size_bytes = head["ContentLength"]

    if file_size_bytes > MAX_FILE_SIZE_BYTES:
        file_size_gb = file_size_bytes / (1024 ** 3)
        raise ValueError(
            f"Video file size ({file_size_gb:.1f} GB) exceeds the processing limit "
            f"of {MAX_FILE_SIZE_BYTES / (1024 ** 3):.0f} GB. "
            "For larger files, consider re-encoding at a lower bitrate."
        )

    # Probe duration via streaming (no full download required)
    duration = get_duration_from_s3(bucket, video_key)

    if duration is None:
        raise ValueError("Could not determine video duration. Ensure the file is a valid MP4.")

    if duration > MAX_DURATION_SECONDS:
        hours = duration / 3600
        raise ValueError(
            f"Video duration ({hours:.1f} hours) exceeds the Amazon Transcribe limit "
            f"of {MAX_DURATION_SECONDS / 3600:.0f} hours."
        )

    # Store metadata for downstream steps
    video_metadata = {
        "video_id": video_id,
        "file_size_bytes": file_size_bytes,
        "duration_seconds": duration,
        "duration_formatted": f"{int(duration // 3600):02d}:{int((duration % 3600) // 60):02d}:{duration % 60:05.2f}",
    }

    metadata_key = f"metadata/{video_id}/input-metadata.json"
    s3.put_object(
        Bucket=bucket,
        Key=metadata_key,
        Body=json.dumps(video_metadata, indent=2),
    )

    return {
        "statusCode": 200,
        "video_id": video_id,
        "bucket": bucket,
        "duration_seconds": duration,
        "file_size_bytes": file_size_bytes,
    }
