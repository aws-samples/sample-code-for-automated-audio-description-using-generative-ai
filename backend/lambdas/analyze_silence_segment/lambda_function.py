"""Analyze silence segment clips using Twelve Labs Pegasus video model.

Each clip includes context padding around the silence gap to provide
narrative context for more accurate visual descriptions.
"""
import json
import os

import boto3
from botocore.client import Config

s3 = boto3.client("s3")

MODEL_ID = os.environ.get("PEGASUS_MODEL_ID", "us.twelvelabs.pegasus-1-2-v1:0")
INFERENCE_PROFILE_ARN = os.environ.get("PEGASUS_INFERENCE_PROFILE_ARN", "")

# Minimum segment duration (seconds) for Pegasus to accept
MIN_SEGMENT_DURATION = 1.0


def create_bedrock_client():
    """Create a Bedrock client with the inference profile header."""
    client = boto3.client(
        "bedrock-runtime",
        region_name=os.environ.get("AWS_REGION", "us-east-1"),
        config=Config(signature_version="v4"),
    )
    client.meta.events.register(
        "before-call.bedrock-runtime.InvokeModel",
        lambda params, **kwargs: params["headers"].update(
            {"X-Amzn-Bedrock-Inference-Profile-Arn": INFERENCE_PROFILE_ARN}
        ),
    )
    return client


def lambda_handler(event, context):
    video_id = event["video_id"]
    bucket = event["bucket"]
    bucket_owner = context.invoked_function_arn.split(":")[4]

    bedrock = create_bedrock_client()

    # Load silence segment metadata
    metadata_key = f"silence-segments/{video_id}/segments-metadata.json"
    metadata_obj = s3.get_object(Bucket=bucket, Key=metadata_key)
    segments = json.loads(metadata_obj["Body"].read())["segments"]

    segment_analyses = []

    # Accumulate Bedrock token usage across all segment invocations.
    # Skipped/too-short/errored segments contribute 0.
    total_input_tokens = 0
    total_output_tokens = 0
    # Accumulate video-seconds submitted to Pegasus. Pegasus INPUT is billed
    # per second of VIDEO (not per input token), so this is the billable input
    # quantity. Count every segment whose clip is actually submitted to Pegasus
    # (duration >= MIN_SEGMENT_DURATION); too-short/skipped segments contribute
    # 0. Errored segments still count their video-seconds since the clip was
    # submitted before the error.
    total_video_seconds = 0.0

    for segment in segments:
        if segment["duration"] < MIN_SEGMENT_DURATION:
            segment_analyses.append({
                "segment_index": segment["segment_index"],
                "start_time": segment["start_time"],
                "end_time": segment["end_time"],
                "duration": segment["duration"],
                "analysis": f"Segment too short ({segment['duration']:.1f}s) for video analysis.",
            })
            continue

        # Clip is submitted to Pegasus below: count its video-seconds as billable
        # input regardless of whether the invocation later errors.
        total_video_seconds += segment["duration"]

        s3_uri = f"s3://{bucket}/{segment['s3_key']}"

        prompt = (
            "You are analyzing a video segment to support audio description (described video) "
            "for viewers who are blind or have low vision. "
            "Describe the main visual elements that a viewer needs to know to understand "
            "what is happening on screen. Focus on:\n"
            "- Actions being performed and by whom\n"
            "- Settings and scene changes\n"
            "- Costumes, body language, and facial expressions that convey meaning\n"
            "- On-screen text, graphics, or titles\n"
            "- Only describe what is visually observable — do not infer motivations, "
            "mental states, or interpret meaning beyond what is shown.\n\n"
            "This description will be used to generate a spoken narration inserted "
            "during a pause in dialogue."
        )

        request_body = {
            "inputPrompt": prompt,
            "mediaSource": {
                "s3Location": {"uri": s3_uri, "bucketOwner": bucket_owner}
            },
            "temperature": 0.2,
            "maxOutputTokens": 2048,
        }

        try:
            response = bedrock.invoke_model(
                modelId=MODEL_ID,
                contentType="application/json",
                accept="application/json",
                body=json.dumps(request_body),
            )
            result = json.loads(response["body"].read().decode())
            analysis = (
                result.get("message")
                or result.get("output", {}).get("message")
                or result.get("content", [{}])[0].get("text")
                or result.get("completion")
                or json.dumps(result)
            )

            # Accumulate token usage. Prefer the parsed response body
            # (InputTokenCount/OutputTokenCount), falling back to the Bedrock
            # response metadata headers when the body omits the counts.
            headers = response.get("ResponseMetadata", {}).get("HTTPHeaders", {})
            input_tokens = (
                result.get("InputTokenCount")
                or result.get("usage", {}).get("input_tokens")
                or headers.get("x-amzn-bedrock-input-token-count")
                or 0
            )
            output_tokens = (
                result.get("OutputTokenCount")
                or result.get("usage", {}).get("output_tokens")
                or headers.get("x-amzn-bedrock-output-token-count")
                or 0
            )
            total_input_tokens += int(input_tokens)
            total_output_tokens += int(output_tokens)
        except Exception as e:
            print(f"Pegasus error for segment {segment['segment_index']}: {e}")
            analysis = f"Error analyzing segment: {e}"

        segment_analyses.append({
            "segment_index": segment["segment_index"],
            "start_time": segment["start_time"],
            "end_time": segment["end_time"],
            "duration": segment["duration"],
            "analysis": analysis,
        })

    output_key = f"analyses/{video_id}/segment-analyses.json"
    s3.put_object(
        Bucket=bucket,
        Key=output_key,
        Body=json.dumps({"segment_analyses": segment_analyses}, indent=2),
    )

    return {
        "statusCode": 200,
        "video_id": video_id,
        "bucket": bucket,
        "segments_analyzed": len(segment_analyses),
        "cost_metadata": {
            "pegasus_video_seconds": total_video_seconds,
            "bedrock_input_tokens": total_input_tokens,
            "bedrock_output_tokens": total_output_tokens,
        },
    }
