"""Start a DVI pipeline execution."""
import json
import os
import re
import time

import boto3

BUCKET = os.environ.get("BUCKET_NAME", "")
STATE_MACHINE_ARN = os.environ.get("STATE_MACHINE_ARN", "")

sfn = boto3.client("stepfunctions")

CORS_HEADERS = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
}

# Allow alphanumeric, hyphens, and underscores only
VIDEO_ID_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_\-]{0,127}$")

# Default minimum silence gap (seconds)
DEFAULT_MIN_SILENCE = 4.0


def lambda_handler(event, context):
    try:
        body = json.loads(event.get("body", "{}"))
    except (json.JSONDecodeError, TypeError):
        return {
            "statusCode": 400,
            "headers": CORS_HEADERS,
            "body": json.dumps({"error": "Invalid JSON body"}),
        }

    video_id = body.get("video_id")
    if not video_id:
        return {
            "statusCode": 400,
            "headers": CORS_HEADERS,
            "body": json.dumps({"error": "Missing required field: video_id"}),
        }

    if not VIDEO_ID_PATTERN.match(video_id):
        return {
            "statusCode": 400,
            "headers": CORS_HEADERS,
            "body": json.dumps({"error": "Invalid video_id. Must be alphanumeric with hyphens/underscores, max 128 chars."}),
        }

    # Optional pipeline parameters
    min_silence_duration = body.get("min_silence_duration", DEFAULT_MIN_SILENCE)
    try:
        min_silence_duration = float(min_silence_duration)
        if min_silence_duration < 2.0 or min_silence_duration > 30.0:
            raise ValueError()
    except (ValueError, TypeError):
        return {
            "statusCode": 400,
            "headers": CORS_HEADERS,
            "body": json.dumps({"error": "min_silence_duration must be between 2 and 30 seconds."}),
        }

    timestamp = int(time.time())

    try:
        response = sfn.start_execution(
            stateMachineArn=STATE_MACHINE_ARN,
            name=f"{video_id}-{timestamp}",
            input=json.dumps({
                "video_id": video_id,
                "bucket": BUCKET,
                "min_silence_duration": min_silence_duration,
            }),
        )

        return {
            "statusCode": 200,
            "headers": CORS_HEADERS,
            "body": json.dumps({
                "execution_arn": response["executionArn"],
                "start_date": response["startDate"].isoformat().replace("+00:00", "Z"),
            }),
        }
    except Exception as e:
        print(f"Failed to start execution: {e}")
        return {
            "statusCode": 500,
            "headers": CORS_HEADERS,
            "body": json.dumps({"error": "Failed to start execution"}),
        }
