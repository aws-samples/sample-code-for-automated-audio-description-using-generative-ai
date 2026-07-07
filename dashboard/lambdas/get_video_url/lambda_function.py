import json
import os
from urllib.parse import unquote

import boto3

BUCKET = os.environ.get("BUCKET_NAME", "")

s3 = boto3.client("s3")

CORS_HEADERS = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
}

# Allowed S3 key prefixes for presigned URL generation
ALLOWED_PREFIXES = ("final/", "input/")


def lambda_handler(event, context):
    try:
        raw_key = event.get("pathParameters", {}).get("id", "")
        key = unquote(raw_key)

        # Validate key prefix to prevent unauthorized access to other objects
        if not key.startswith(ALLOWED_PREFIXES):
            return {
                "statusCode": 403,
                "headers": CORS_HEADERS,
                "body": json.dumps({"error": "Access denied: invalid key prefix"}),
            }

        # Validate key doesn't contain path traversal
        if ".." in key:
            return {
                "statusCode": 400,
                "headers": CORS_HEADERS,
                "body": json.dumps({"error": "Invalid key"}),
            }

        url = s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": BUCKET, "Key": key},
            ExpiresIn=3600,
        )

        return {
            "statusCode": 200,
            "headers": CORS_HEADERS,
            "body": json.dumps({"url": url}),
        }
    except Exception as e:
        return {
            "statusCode": 500,
            "headers": CORS_HEADERS,
            "body": json.dumps({"error": "Failed to generate URL"}),
        }
