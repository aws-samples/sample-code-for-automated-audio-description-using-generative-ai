import json
import os
import logging
import urllib.parse
from datetime import datetime, timezone

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

STATE_MACHINE_ARN = os.environ.get("STATE_MACHINE_ARN", "")
# Backward compatibility aliases
V1_STATE_MACHINE_ARN = STATE_MACHINE_ARN
V2_STATE_MACHINE_ARN = STATE_MACHINE_ARN
V3_STATE_MACHINE_ARN = STATE_MACHINE_ARN

sfn = boto3.client("stepfunctions")
lambda_client = boto3.client("lambda")

CORS_HEADERS = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
}

# ---- Pricing (us-east-1, as of 2025) ----
PRICING = {
    "step_functions": {"per_transition": 0.000025},
    "lambda": {"per_request": 0.0000002, "per_gb_second": 0.0000166667},
    "transcribe": {"per_second": 0.00040},
    "bedrock": {
        "pegasus": {
            # Twelve Labs Pegasus 1.2 on Bedrock (on-demand, us-east-1, Global
            # cross-region inference). Pegasus INPUT is billed per second of
            # VIDEO submitted, NOT per input token — input tokens are not billed.
            "input_per_video_second": 0.00049,   # $0.00049 / video-second
            "output_per_1k_tokens": 0.0075,       # $7.50 / 1M output tokens
        },
        "claude_sonnet": {"input_per_1k_tokens": 0.003, "output_per_1k_tokens": 0.015},
    },
    "polly": {"per_character_neural": 0.000016, "per_character_standard": 0.000004},
    "dynamodb": {"per_wcu": 0.00000125, "per_rcu": 0.00000025},
    "s3": {"per_put": 0.000005, "per_get": 0.0000004},
}

# Version-specific state-to-Lambda-function mappings
STATE_TO_FUNCTION = {
    "V1": {
        "TranscribeVideo": "transcribe-video-lambda-dvi",
        "DetectSilences": "silence-detection-lambda-dvi",
        "SplitIntoChunks": "extract-silence-clips-lambda-dvi",
        "AnalyzeChunks": "analyze-silence-clips-lambda-dvi",
        "GenerateDVI": "generate-dvi-lambda-dvi",
        "SynthesizeAudio": "synthesize-dvi-audio-lambda-dvi",
        "MixAudioTracks": "mix-audio-tracks-lambda-dvi",
        "WriteSummaryToDynamoDB": "write-summary-dynamodb-dvi",
        "WriteTxtSummaryToS3": "write-summary-s3-dvi",
    },
    "V2": {
        "TranscribeVideo": "v2-transcribe-video-dvi",
        "DetectSilences": "v2-silence-detection-dvi",
        "SplitIntoChunks": "v2-split-video-dvi",
        "ExtractSilenceSegments": "v2-extract-silence-segments-dvi",
        "AnalyzeSilenceSegments": "v2-analyze-silence-segment-pegasus-dvi",
        "GenerateDVI": "v2-generate-dvi-dvi",
        "SynthesizeAudio": "v2-synthesize-dvi-audio-dvi",
        "MixAudioTracks": "v2-mix-audio-tracks-dvi",
        "WriteSummaryToDynamoDB": "v2-write-summary-dynamodb-dvi",
        "WriteTxtSummaryToS3": "v2-write-summary-s3-dvi",
    },
    "V3": {
        "TranscribeVideo": "v3-transcribe-video-dvi",
        "DetectSilences": "v3-silence-detection-dvi",
        "SplitIntoChunks": "v3-split-video-dvi",
        "SummarizeFullVideo": "v3-summarize-full-video-dvi",
        "ExtractSilenceSegments": "v3-extract-silence-segments-dvi",
        "AnalyzeSilenceSegments": "v3-analyze-silence-segment-pegasus-dvi",
        "GenerateDVI": "v3-generate-dvi-dvi",
        "SynthesizeAudio": "v3-synthesize-dvi-audio-dvi",
        "MixAudioTracks": "v3-mix-audio-tracks-dvi",
        "WriteSummaryToDynamoDB": "v3-write-summary-dynamodb-dvi",
        "WriteTxtSummaryToS3": "v3-write-summary-s3-dvi",
    },
}

# Which downstream services each state uses
STATE_SERVICES = {
    "TranscribeVideo": ["transcribe", "s3"],
    "DetectSilences": ["s3"],
    "SplitIntoChunks": ["s3"],
    "SummarizeFullVideo": ["bedrock", "s3"],
    "ExtractSilenceSegments": ["s3"],
    "AnalyzeChunks": ["bedrock", "s3"],
    "AnalyzeSilenceSegments": ["bedrock", "s3"],
    "GenerateDVI": ["bedrock", "s3"],
    "SynthesizeAudio": ["polly", "s3"],
    "MixAudioTracks": ["s3"],
    "WriteSummaryToDynamoDB": ["dynamodb"],
    "WriteTxtSummaryToS3": ["s3"],
}

# Maps state names to their ResultPath keys in the execution output.
#
# The deployed Step Functions pipeline builds each task with the `invoke_step`
# helper (see infrastructure/pipeline_stack.py), which assigns a ResultPath of
# "$." + state_name.lower().replace(" ", "_") + "_result". The four in-scope
# states below therefore use the deployed convention keys (not the legacy ones).
STATE_TO_RESULT_PATH = {
    # In-scope deployed states (must match the invoke_step convention)
    "ValidateInput": "validateinput_result",
    "AnalyzeSegments": "analyzesegments_result",
    "GenerateDVI": "generatedvi_result",
    "SynthesizeAudio": "synthesizeaudio_result",
    # Legacy / other states
    "TranscribeVideo": "transcribe_result",
    "DetectSilences": "silence_result",
    "SplitIntoChunks": "chunk_result",
    "AnalyzeChunks": "analysis_result",
    "AnalyzeSilenceSegments": "analysis_result",
    "SummarizeFullVideo": "summary_result",
    "MixAudioTracks": "final_result",
    "WriteSummaryToDynamoDB": "summary_result",
    "WriteTxtSummaryToS3": "s3_summary_result",
}


def _get_pipeline_version(state_machine_arn):
    """Determine pipeline version from the state machine ARN in execution details."""
    arn_to_version = {
        V1_STATE_MACHINE_ARN: "V1",
        V2_STATE_MACHINE_ARN: "V2",
        V3_STATE_MACHINE_ARN: "V3",
    }
    return arn_to_version.get(state_machine_arn, "V1")


def _get_execution_history(execution_arn):
    """Get all execution history events with pagination."""
    events = []
    params = {"executionArn": execution_arn, "maxResults": 1000}
    while True:
        resp = sfn.get_execution_history(**params)
        events.extend(resp.get("events", []))
        next_token = resp.get("nextToken")
        if not next_token:
            break
        params["nextToken"] = next_token
    return events


def _extract_invocations(events):
    """Parse TaskStateEntered/TaskStateExited events to extract per-step durations and outputs."""
    invocations = []
    task_started = {}

    for event in events:
        etype = event["type"]
        ts = event["timestamp"]

        if etype == "TaskStateEntered":
            state_name = event["stateEnteredEventDetails"]["name"]
            task_started[state_name] = ts

        elif etype == "TaskStateExited":
            state_name = event["stateExitedEventDetails"]["name"]
            start = task_started.get(state_name)
            if start:
                duration = (ts - start).total_seconds()
                output_raw = event["stateExitedEventDetails"].get("output", "{}")
                try:
                    output = json.loads(output_raw)
                except (json.JSONDecodeError, TypeError):
                    output = {}
                invocations.append({
                    "state": state_name,
                    "start": start,
                    "end": ts,
                    "duration_seconds": duration,
                    "output": output,
                })

    return invocations


def _get_lambda_memory(func_name):
    """Get Lambda memory size; fall back to 512MB on failure."""
    try:
        config = lambda_client.get_function_configuration(FunctionName=func_name)
        return config.get("MemorySize", 512)
    except Exception as e:
        logger.warning(f"Could not get config for {func_name}: {e}")
        return 512


def _estimate_downstream_costs(costs, invocations, version):
    """Estimate costs for downstream services using cost_metadata when available,
    falling back to duration-based estimates otherwise."""

    for inv in invocations:
        state = inv["state"]
        output = inv.get("output", {})

        # Extract cost_metadata from the correct result path
        result_key = STATE_TO_RESULT_PATH.get(state, "")
        step_result = output.get(result_key, {})
        payload = step_result.get("Payload", step_result)
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except (json.JSONDecodeError, TypeError):
                payload = {}

        meta = payload.get("cost_metadata", {})

        # Transcribe — sourced from ValidateInput's duration_seconds.
        # (The Transcribe states' result_selector strips usage, so the audio
        # duration is recovered from the ValidateInput payload instead.)
        if state == "ValidateInput":
            duration_secs = payload.get("duration_seconds", 0) or 0
            if duration_secs > 0:
                cost = duration_secs * PRICING["transcribe"]["per_second"]
                costs.append({
                    "service": "Transcribe",
                    "description": "Audio transcription",
                    "usage": f"{duration_secs} seconds",
                    "cost_usd": round(cost, 8),
                })
            else:
                # Graceful degradation: duration-based estimate, clearly labeled.
                est_secs = inv["duration_seconds"] * 0.8
                cost = est_secs * PRICING["transcribe"]["per_second"]
                costs.append({
                    "service": "Transcribe",
                    "description": "Audio transcription (estimated)",
                    "usage": f"{round(est_secs, 1)} seconds",
                    "cost_usd": round(cost, 8),
                })

        # Bedrock - AnalyzeChunks (V1) / AnalyzeSilenceSegments (V2/V3) /
        # AnalyzeSegments (deployed) use Pegasus
        if state in ("AnalyzeChunks", "AnalyzeSilenceSegments", "AnalyzeSegments"):
            video_seconds = meta.get("pegasus_video_seconds", 0)
            output_tokens = meta.get("bedrock_output_tokens", 0)
            if video_seconds > 0 or output_tokens > 0:
                pricing = PRICING["bedrock"]["pegasus"]
                input_cost = video_seconds * pricing["input_per_video_second"]
                output_cost = (output_tokens / 1000) * pricing["output_per_1k_tokens"]
                costs.append({
                    "service": "Bedrock",
                    "description": "Pegasus video input",
                    "usage": f"{round(video_seconds, 1)} video-sec",
                    "cost_usd": round(input_cost, 8),
                })
                costs.append({
                    "service": "Bedrock",
                    "description": "Pegasus output",
                    "usage": f"{output_tokens} tokens",
                    "cost_usd": round(output_cost, 8),
                })
            else:
                # Graceful degradation: estimate video-seconds from wall-clock
                # duration and price at the real per-video-second rate. Clearly
                # labeled so it is never mistaken for a confirmed cost.
                est_video_secs = inv["duration_seconds"] * 0.7
                est_cost = est_video_secs * PRICING["bedrock"]["pegasus"]["input_per_video_second"]
                costs.append({
                    "service": "Bedrock",
                    "description": "Pegasus (estimated)",
                    "usage": f"{round(est_video_secs, 1)} video-sec",
                    "cost_usd": round(est_cost, 8),
                })

        # Bedrock - SummarizeFullVideo (V3 only) uses Pegasus
        if state == "SummarizeFullVideo":
            video_seconds = meta.get("pegasus_video_seconds", 0)
            output_tokens = meta.get("bedrock_output_tokens", 0)
            if video_seconds > 0 or output_tokens > 0:
                pricing = PRICING["bedrock"]["pegasus"]
                input_cost = video_seconds * pricing["input_per_video_second"]
                output_cost = (output_tokens / 1000) * pricing["output_per_1k_tokens"]
                costs.append({
                    "service": "Bedrock",
                    "description": "Pegasus summary input",
                    "usage": f"{round(video_seconds, 1)} video-sec",
                    "cost_usd": round(input_cost, 8),
                })
                costs.append({
                    "service": "Bedrock",
                    "description": "Pegasus summary output",
                    "usage": f"{output_tokens} tokens",
                    "cost_usd": round(output_cost, 8),
                })
            else:
                est_video_secs = inv["duration_seconds"] * 0.7
                est_cost = est_video_secs * PRICING["bedrock"]["pegasus"]["input_per_video_second"]
                costs.append({
                    "service": "Bedrock",
                    "description": "Pegasus summary (estimated)",
                    "usage": f"{round(est_video_secs, 1)} video-sec",
                    "cost_usd": round(est_cost, 8),
                })

        # Bedrock - GenerateDVI uses Claude Sonnet
        if state == "GenerateDVI":
            input_tokens = meta.get("bedrock_input_tokens", 0)
            output_tokens = meta.get("bedrock_output_tokens", 0)
            if input_tokens > 0 or output_tokens > 0:
                pricing = PRICING["bedrock"]["claude_sonnet"]
                input_cost = (input_tokens / 1000) * pricing["input_per_1k_tokens"]
                output_cost = (output_tokens / 1000) * pricing["output_per_1k_tokens"]
                costs.append({
                    "service": "Bedrock",
                    "description": "Claude Sonnet input",
                    "usage": f"{input_tokens} tokens",
                    "cost_usd": round(input_cost, 8),
                })
                costs.append({
                    "service": "Bedrock",
                    "description": "Claude Sonnet output",
                    "usage": f"{output_tokens} tokens",
                    "cost_usd": round(output_cost, 8),
                })
            else:
                # Graceful degradation: Claude usage cannot be estimated from
                # duration, so flag it as unavailable rather than a silent $0.
                costs.append({
                    "service": "Bedrock",
                    "description": "Claude Sonnet (usage unavailable)",
                    "usage": "unavailable",
                    "cost_usd": 0.0,
                })

        # Polly
        if state == "SynthesizeAudio":
            chars = meta.get("polly_characters", 0)
            if chars > 0:
                cost = chars * PRICING["polly"]["per_character_neural"]
                costs.append({
                    "service": "Polly",
                    "description": "Speech synthesis (neural)",
                    "usage": f"{chars} characters",
                    "cost_usd": round(cost, 8),
                })
            else:
                # Graceful degradation: flag unavailable rather than a silent $0.
                costs.append({
                    "service": "Polly",
                    "description": "Speech synthesis (usage unavailable)",
                    "usage": "unavailable",
                    "cost_usd": 0.0,
                })

        # DynamoDB
        if state == "WriteSummaryToDynamoDB":
            wcus = meta.get("dynamodb_wcus", 0)
            if wcus > 0:
                cost = wcus * PRICING["dynamodb"]["per_wcu"]
                costs.append({
                    "service": "DynamoDB",
                    "description": "Write operations",
                    "usage": f"{wcus} WCUs",
                    "cost_usd": round(cost, 8),
                })
            else:
                costs.append({
                    "service": "DynamoDB",
                    "description": "Write (estimated 1)",
                    "usage": "1 WCUs",
                    "cost_usd": round(PRICING["dynamodb"]["per_wcu"], 8),
                })

        # S3 operations
        services = STATE_SERVICES.get(state, [])
        if "s3" in services:
            puts = meta.get("s3_puts", 0)
            gets = meta.get("s3_gets", 0)
            if puts > 0 or gets > 0:
                s3_cost = (puts * PRICING["s3"]["per_put"]) + (gets * PRICING["s3"]["per_get"])
                costs.append({
                    "service": "S3",
                    "description": f"{state} ({puts}P/{gets}G)",
                    "usage": f"{puts + gets} requests",
                    "cost_usd": round(s3_cost, 8),
                })


def _calculate_cost(execution_arn):
    """Calculate the full cost breakdown for a single execution."""
    execution = sfn.describe_execution(executionArn=execution_arn)
    events = _get_execution_history(execution_arn)
    invocations = _extract_invocations(events)

    state_machine_arn = execution["stateMachineArn"]
    version = _get_pipeline_version(state_machine_arn)
    func_map = STATE_TO_FUNCTION.get(version, STATE_TO_FUNCTION["V1"])

    start_time = execution["startDate"]
    stop_time = execution.get("stopDate", datetime.now(timezone.utc))
    total_duration = (stop_time - start_time).total_seconds()

    costs = []

    # 1. Step Functions state transitions
    transition_count = len([e for e in events if e["type"].endswith("StateEntered")])
    sf_cost = transition_count * PRICING["step_functions"]["per_transition"]
    costs.append({
        "service": "Step Functions",
        "description": f"{transition_count} transitions",
        "usage": f"{transition_count} transitions",
        "cost_usd": round(sf_cost, 8),
    })

    # 2. Lambda costs per function
    for inv in invocations:
        func_name = func_map.get(inv["state"])
        if not func_name:
            continue

        memory_mb = _get_lambda_memory(func_name)
        memory_gb = memory_mb / 1024

        duration_sec = inv["duration_seconds"]
        gb_seconds = memory_gb * duration_sec

        request_cost = PRICING["lambda"]["per_request"]
        compute_cost = gb_seconds * PRICING["lambda"]["per_gb_second"]
        lambda_cost = request_cost + compute_cost

        costs.append({
            "service": "Lambda",
            "description": func_name.replace("-lambda-dvi", "").replace("-dvi", ""),
            "usage": f"{round(duration_sec, 1)} sec @ {memory_mb}MB",
            "cost_usd": round(lambda_cost, 8),
        })

    # 3. Estimate downstream service costs
    _estimate_downstream_costs(costs, invocations, version)

    total_cost = sum(c["cost_usd"] for c in costs)

    return {
        "execution_arn": execution_arn,
        "state_machine": state_machine_arn,
        "status": execution["status"],
        "start_time": start_time.isoformat(),
        "end_time": stop_time.isoformat(),
        "duration_seconds": round(total_duration, 2),
        "cost_breakdown": costs,
        "total_cost_usd": round(total_cost, 6),
    }


def lambda_handler(event, context):
    try:
        arn = (event.get("pathParameters") or {}).get("arn", "")
        arn = urllib.parse.unquote(arn) if arn else ""

        if not arn:
            return {
                "statusCode": 400,
                "headers": CORS_HEADERS,
                "body": json.dumps({"error": "Missing required parameter: execution ARN"}),
            }

        try:
            report = _calculate_cost(arn)
        except sfn.exceptions.ExecutionDoesNotExist:
            return {
                "statusCode": 404,
                "headers": CORS_HEADERS,
                "body": json.dumps({"error": f"Execution not found: {arn}"}),
            }

        return {
            "statusCode": 200,
            "headers": CORS_HEADERS,
            "body": json.dumps(report),
        }
    except Exception as e:
        logger.error(f"Failed to calculate cost: {e}", exc_info=True)
        return {
            "statusCode": 500,
            "headers": CORS_HEADERS,
            "body": json.dumps({"error": f"Failed to calculate cost: {str(e)}"}),
        }
