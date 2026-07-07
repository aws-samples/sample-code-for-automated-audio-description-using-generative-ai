import json
import urllib.parse

import boto3

sfn = boto3.client("stepfunctions")

CORS_HEADERS = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
}


def build_steps(events):
    """Iterate execution history events and build a list of step dicts."""
    steps = {}
    step_order = []

    for event in events:
        event_type = event.get("type", "")

        if event_type == "TaskStateEntered":
            details = event.get("stateEnteredEventDetails", {})
            name = details.get("name", "")
            if name and name not in steps:
                step_order.append(name)
            steps[name] = {
                "name": name,
                "status": "running",
                "entered_at": event["timestamp"].isoformat().replace("+00:00", "Z"),
                "exited_at": None,
            }

        elif event_type == "TaskStateExited":
            details = event.get("stateExitedEventDetails", {})
            name = details.get("name", "")
            if name in steps:
                steps[name]["status"] = "succeeded"
                steps[name]["exited_at"] = event["timestamp"].isoformat().replace("+00:00", "Z")

        elif event_type == "TaskStateFailed":
            details = event.get("stateExitedEventDetails", {})
            name = details.get("name", "")
            if name in steps:
                steps[name]["status"] = "failed"
                steps[name]["exited_at"] = event["timestamp"].isoformat().replace("+00:00", "Z")

    return [steps[name] for name in step_order]


def lambda_handler(event, context):
    try:
        arn = event.get("pathParameters", {}).get("arn", "")
        arn = urllib.parse.unquote(arn)

        desc = sfn.describe_execution(executionArn=arn)

        start_date = desc["startDate"].isoformat().replace("+00:00", "Z")
        stop_date = None
        if desc.get("stopDate"):
            stop_date = desc["stopDate"].isoformat().replace("+00:00", "Z")

        history = sfn.get_execution_history(executionArn=arn)
        steps = build_steps(history.get("events", []))

        return {
            "statusCode": 200,
            "headers": CORS_HEADERS,
            "body": json.dumps({
                "execution_arn": arn,
                "status": desc["status"],
                "start_date": start_date,
                "stop_date": stop_date,
                "steps": steps,
                "error": desc.get("error"),
                "cause": desc.get("cause"),
            }),
        }
    except Exception as e:
        return {
            "statusCode": 500,
            "headers": CORS_HEADERS,
            "body": json.dumps({"error": f"Failed to get execution status: {str(e)}"}),
        }
