"""Record a structured, per-execution processing summary in DynamoDB.

Persists aggregate metrics (silence/audio totals, pass/fail counts) and
per-segment details (start time, DVI text, audio duration, fit check) keyed by
video_id + execution_id. This is the queryable record the dashboard reads back
to render the summary bar and the per-segment PASS/FAIL fit badges.
"""
import json
import os
from datetime import datetime
from decimal import Decimal

import boto3

s3 = boto3.client("s3")
REGION = os.environ.get("AWS_REGION", "us-east-1")
TABLE_NAME = os.environ.get("TABLE_NAME", "dvi-processing-summary")

dynamodb = boto3.resource("dynamodb", region_name=REGION)
table = dynamodb.Table(TABLE_NAME)


def lambda_handler(event, context):
    video_id = event["video_id"]
    bucket = event["bucket"]
    execution_id = context.aws_request_id

    # Get silences data
    silence_key = f"transcribe/{video_id}/silences.json"
    silence_obj = s3.get_object(Bucket=bucket, Key=silence_key)
    silences = json.loads(silence_obj["Body"].read())["silences"]

    # Get DVI segments
    dvi_key = f"dvi/{video_id}/dvi-segments.json"
    dvi_obj = s3.get_object(Bucket=bucket, Key=dvi_key)
    dvi_segments = json.loads(dvi_obj["Body"].read())["segments"]

    # Get audio metadata
    audio_key = f"audio/{video_id}/audio-metadata.json"
    audio_obj = s3.get_object(Bucket=bucket, Key=audio_key)
    audio_files = json.loads(audio_obj["Body"].read())["audio_files"]

    # Build segment details
    segment_details = []
    for audio in audio_files:
        segment_info = {
            "index": audio["index"],
            "start_time": Decimal(str(audio["start"])),
            "silence_duration": Decimal(str(audio["silence_duration"])),
            "dvi_text": audio["text"],
            "audio_duration": (
                Decimal(str(audio["actual_audio_duration"]))
                if audio.get("actual_audio_duration")
                else None
            ),
            "duration_check": (
                "PASS"
                if audio.get("actual_audio_duration")
                and audio["actual_audio_duration"] <= audio["silence_duration"]
                else "FAIL"
            ),
        }
        segment_details.append(segment_info)

    total_silence_duration = sum(s["duration"] for s in silences)
    total_audio_duration = sum(
        a.get("actual_audio_duration", 0)
        for a in audio_files
        if a.get("actual_audio_duration")
    )
    failed_segments = [s for s in segment_details if s["duration_check"] == "FAIL"]

    item = {
        "video_id": video_id,
        "execution_id": execution_id,
        "timestamp": datetime.utcnow().isoformat(),
        "bucket": bucket,
        "pipeline_version": "context-window",
        "summary": {
            "total_silence_segments": len(silences),
            "total_silence_duration": Decimal(str(total_silence_duration)),
            "total_audio_duration": Decimal(str(total_audio_duration)),
            "segments_passed": len(segment_details) - len(failed_segments),
            "segments_failed": len(failed_segments),
        },
        "segments": segment_details,
    }

    table.put_item(Item=item)

    return {
        "statusCode": 200,
        "video_id": video_id,
        "execution_id": execution_id,
        "summary_written": True,
        "total_segments": len(segment_details),
        "failed_segments": len(failed_segments),
    }
