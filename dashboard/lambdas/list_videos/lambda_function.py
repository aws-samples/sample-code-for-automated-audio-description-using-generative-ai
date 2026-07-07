"""List processed videos in the final/ prefix of the S3 bucket."""
import json
import os
import re

import boto3

BUCKET = os.environ.get("BUCKET_NAME", "")
KEY_PATTERN = re.compile(r"^final/(.+)-(\d{8}-\d{6})\.mp4$")

s3 = boto3.client("s3")

CORS_HEADERS = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
}


def parse_video_key(obj):
    """Parse an S3 object into a VideoEntry dict, or None if key doesn't match."""
    key = obj["Key"]
    match = KEY_PATTERN.match(key)
    if not match:
        return None

    video_id, timestamp = match.groups()
    filename = key.split("/", 1)[1]

    return {
        "key": key,
        "filename": filename,
        "video_id": video_id,
        "timestamp": timestamp,
        "last_modified": obj["LastModified"].isoformat().replace("+00:00", "Z"),
        "size_bytes": obj["Size"],
    }


def lambda_handler(event, context):
    try:
        response = s3.list_objects_v2(Bucket=BUCKET, Prefix="final/")
        contents = response.get("Contents", [])

        videos = []
        for obj in contents:
            entry = parse_video_key(obj)
            if entry:
                videos.append(entry)

        videos.sort(key=lambda v: v["last_modified"], reverse=True)

        return {
            "statusCode": 200,
            "headers": CORS_HEADERS,
            "body": json.dumps({"videos": videos}),
        }
    except Exception as e:
        print(f"Failed to list videos: {e}")
        return {
            "statusCode": 500,
            "headers": CORS_HEADERS,
            "body": json.dumps({"error": "Failed to list videos"}),
        }
