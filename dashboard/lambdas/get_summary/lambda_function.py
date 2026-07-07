import json
import os
from decimal import Decimal

import boto3

TABLE_NAME = os.environ.get("TABLE_NAME", "dvi-processing-summary")

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(TABLE_NAME)

CORS_HEADERS = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
}


def decimal_to_float(obj):
    """Recursively convert Decimal values to float for JSON serialization."""
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, dict):
        return {k: decimal_to_float(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [decimal_to_float(item) for item in obj]
    return obj


def lambda_handler(event, context):
    try:
        video_id = event.get("pathParameters", {}).get("id", "")

        # Table uses composite key (video_id + execution_id).
        # Query by partition key to get the most recent execution.
        response = table.query(
            KeyConditionExpression="video_id = :vid",
            ExpressionAttributeValues={":vid": video_id},
            ScanIndexForward=False,  # Most recent first
            Limit=1,
        )

        items = response.get("Items", [])
        if not items:
            return {
                "statusCode": 200,
                "headers": CORS_HEADERS,
                "body": json.dumps({"summary": None}),
            }

        result = decimal_to_float(items[0])

        return {
            "statusCode": 200,
            "headers": CORS_HEADERS,
            "body": json.dumps(result),
        }
    except Exception as e:
        return {
            "statusCode": 500,
            "headers": CORS_HEADERS,
            "body": json.dumps({
                "error": "Failed to retrieve summary",
            }),
        }
