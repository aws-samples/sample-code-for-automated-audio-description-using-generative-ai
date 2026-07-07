import json
import os

import boto3

BUCKET = os.environ.get("BUCKET_NAME", "")

s3 = boto3.client("s3")

CORS_HEADERS = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
}


def lambda_handler(event, context):
    try:
        response = s3.list_objects_v2(Bucket=BUCKET, Prefix="input/")
        contents = response.get("Contents", [])

        videos = []
        for obj in contents:
            key = obj["Key"]
            if not key.endswith(".mp4"):
                continue

            # Derive video_id by stripping "input/" prefix and ".mp4" extension
            video_id = key[len("input/"):-len(".mp4")]
            if not video_id:
                continue

            size_mb = round(obj["Size"] / (1024 * 1024), 1)

            videos.append({
                "video_id": video_id,
                "key": key,
                "size_mb": size_mb,
                "last_modified": obj["LastModified"].isoformat().replace("+00:00", "Z"),
            })

        videos.sort(key=lambda v: v["video_id"])

        return {
            "statusCode": 200,
            "headers": CORS_HEADERS,
            "body": json.dumps({"videos": videos}),
        }
    except Exception as e:
        return {
            "statusCode": 500,
            "headers": CORS_HEADERS,
            "body": json.dumps({"error": f"Failed to list input videos: {str(e)}"}),
        }
