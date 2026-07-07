"""List pipeline executions filtered by video ID."""
import json
import os

import boto3

STATE_MACHINE_ARN = os.environ.get("STATE_MACHINE_ARN", "")

sfn = boto3.client("stepfunctions")

CORS_HEADERS = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
}


def lambda_handler(event, context):
    try:
        params = event.get("queryStringParameters") or {}
        video_id = params.get("video_id", "")

        if not video_id:
            return {
                "statusCode": 400,
                "headers": CORS_HEADERS,
                "body": json.dumps({"error": "Missing required parameter: video_id"}),
            }

        executions = []

        if STATE_MACHINE_ARN:
            paginator = sfn.get_paginator("list_executions")
            for page in paginator.paginate(stateMachineArn=STATE_MACHINE_ARN):
                for execution in page.get("executions", []):
                    if video_id in execution["name"]:
                        executions.append({
                            "execution_arn": execution["executionArn"],
                            "name": execution["name"],
                            "status": execution["status"],
                            "start_time": execution["startDate"].isoformat().replace("+00:00", "Z"),
                        })

        executions.sort(key=lambda e: e["start_time"], reverse=True)

        return {
            "statusCode": 200,
            "headers": CORS_HEADERS,
            "body": json.dumps({"executions": executions}),
        }
    except Exception as e:
        print(f"Failed to list executions: {e}")
        return {
            "statusCode": 500,
            "headers": CORS_HEADERS,
            "body": json.dumps({"error": "Failed to list executions"}),
        }
