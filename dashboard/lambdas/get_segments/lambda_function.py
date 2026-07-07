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
        video_id = event.get("pathParameters", {}).get("id", "")

        response = s3.get_object(
            Bucket=BUCKET,
            Key=f"dvi/{video_id}/dvi-segments.json",
        )

        data = json.loads(response["Body"].read().decode("utf-8"))
        segments = data.get("segments", [])

        return {
            "statusCode": 200,
            "headers": CORS_HEADERS,
            "body": json.dumps({"segments": segments}),
        }
    except s3.exceptions.NoSuchKey:
        return {
            "statusCode": 200,
            "headers": CORS_HEADERS,
            "body": json.dumps({
                "segments": [],
                "message": "No DVI segments found for this video",
            }),
        }
    except Exception as e:
        return {
            "statusCode": 500,
            "headers": CORS_HEADERS,
            "body": json.dumps({
                "error": f"Failed to retrieve segments: {str(e)}",
            }),
        }
