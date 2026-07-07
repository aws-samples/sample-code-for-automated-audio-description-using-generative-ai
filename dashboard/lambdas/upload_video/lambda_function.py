"""Generate a presigned URL for uploading a video to the input/ prefix."""
import json
import os
import re

import boto3

BUCKET = os.environ.get("BUCKET_NAME", "")

s3 = boto3.client("s3")

CORS_HEADERS = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
}

# Allow alphanumeric, hyphens, underscores, and dots in filename
FILENAME_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_\-\.]{0,127}\.mp4$")


def lambda_handler(event, context):
    try:
        body = json.loads(event.get("body", "{}"))
    except (json.JSONDecodeError, TypeError):
        return {
            "statusCode": 400,
            "headers": CORS_HEADERS,
            "body": json.dumps({"error": "Invalid JSON body"}),
        }

    filename = body.get("filename", "")
    if not filename:
        return {
            "statusCode": 400,
            "headers": CORS_HEADERS,
            "body": json.dumps({"error": "Missing required field: filename"}),
        }

    if not FILENAME_PATTERN.match(filename):
        return {
            "statusCode": 400,
            "headers": CORS_HEADERS,
            "body": json.dumps({"error": "Invalid filename. Must be alphanumeric with .mp4 extension."}),
        }

    key = f"input/{filename}"

    url = s3.generate_presigned_url(
        "put_object",
        Params={
            "Bucket": BUCKET,
            "Key": key,
            "ContentType": "video/mp4",
        },
        ExpiresIn=3600,
    )

    return {
        "statusCode": 200,
        "headers": CORS_HEADERS,
        "body": json.dumps({"url": url, "key": key}),
    }
