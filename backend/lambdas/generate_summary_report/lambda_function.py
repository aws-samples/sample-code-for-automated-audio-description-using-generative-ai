"""Generate a human-readable text report of the DVI run and store it in S3.

Renders a formatted .txt report listing each silence segment with its
timestamps, duration, and generated DVI narration, then writes it to
summaries/{video_id}-summary-{shortid}.txt for people to read or download.
"""
import json
import uuid
from datetime import datetime

import boto3

s3 = boto3.client("s3")


def format_timestamp(seconds):
    """Convert seconds to HH:MM:SS.mmm format."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:06.3f}"


def build_summary_text(video_id, pipeline_version, narration_records, processing_date=None):
    if processing_date is None:
        processing_date = datetime.utcnow().isoformat() + "Z"

    lines = [
        "DVI Narration Summary",
        "=====================",
        f"Video: {video_id}.mp4",
        f"Pipeline Version: {pipeline_version}",
        f"Processing Date: {processing_date}",
        "",
        "Detected Silences and DVI Narration:",
        "-------------------------------------",
        "",
    ]

    for idx, record in enumerate(narration_records, start=1):
        start = record["start_time"]
        end = record["end_time"]
        duration = round(end - start, 1)
        dvi_text = record.get("dvi_text", "")

        lines.append(f"Segment {idx}:")
        lines.append(f"  Silence Start: {format_timestamp(start)}")
        lines.append(f"  Silence End:   {format_timestamp(end)}")
        lines.append(f"  Duration:      {duration}s")
        lines.append(f'  DVI Narration: "{dvi_text}"')
        lines.append("")

    lines.append("-------------------------------------")
    lines.append(f"Total Silences Detected: {len(narration_records)}")
    lines.append(f"Total DVI Narrations Generated: {len(narration_records)}")
    lines.append("")

    return "\n".join(lines)


def lambda_handler(event, context):
    video_id = event["video_id"]
    bucket = event["bucket"]

    dvi_key = f"dvi/{video_id}/dvi-segments.json"
    dvi_obj = s3.get_object(Bucket=bucket, Key=dvi_key)
    dvi_segments = json.loads(dvi_obj["Body"].read())["segments"]

    narration_records = [
        {
            "start_time": seg["start"],
            "end_time": seg["end"],
            "dvi_text": seg["dvi_text"],
        }
        for seg in dvi_segments
    ]

    summary_text = build_summary_text(
        video_id=video_id,
        pipeline_version="context-window",
        narration_records=narration_records,
    )

    short_id = uuid.uuid4().hex[:8]
    summary_key = f"summaries/{video_id}-summary-{short_id}.txt"
    s3.put_object(
        Bucket=bucket,
        Key=summary_key,
        Body=summary_text,
        ContentType="text/plain",
    )

    return {
        "statusCode": 200,
        "video_id": video_id,
        "bucket": bucket,
        "summary_s3_path": f"s3://{bucket}/{summary_key}",
        "segments_in_summary": len(narration_records),
    }
