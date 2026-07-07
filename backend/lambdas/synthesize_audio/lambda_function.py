"""Synthesize DVI narration text to speech using Amazon Polly."""
import json
import os
from io import BytesIO

import boto3
from mutagen.mp3 import MP3

s3 = boto3.client("s3")
REGION = os.environ.get("AWS_REGION", "us-east-1")
polly = boto3.client("polly", region_name=REGION)


def lambda_handler(event, context):
    video_id = event["video_id"]
    bucket = event["bucket"]

    dvi_key = f"dvi/{video_id}/dvi-segments.json"
    dvi_obj = s3.get_object(Bucket=bucket, Key=dvi_key)
    segments = json.loads(dvi_obj["Body"].read())["segments"]

    audio_files = []
    # Accumulate Polly-billed characters for cost reporting. Synthesis uses
    # TextType="text" (no SSML), so billed characters equal len(dvi_text).
    polly_characters = 0

    for i, segment in enumerate(segments):
        # Use 80% of available silence to leave breathing room
        target_duration = segment["duration"] * 0.8
        max_duration_seconds = max(2, int(target_duration))

        # Use plain text with neural voice for natural-sounding speech.
        # The generate_dvi step already constrains text length to fit the gap.
        response = polly.synthesize_speech(
            Text=segment["dvi_text"],
            TextType="text",
            OutputFormat="mp3",
            VoiceId="Matthew",
            Engine="neural",
        )

        # Billed characters for this segment. Plain text means this equals the
        # input length; cross-check the x-amzn-RequestCharacters response header
        # when present, falling back to len(dvi_text).
        billed_chars = len(segment["dvi_text"])
        request_chars = (
            response.get("ResponseMetadata", {})
            .get("HTTPHeaders", {})
            .get("x-amzn-requestcharacters")
        )
        if request_chars is not None:
            try:
                billed_chars = int(request_chars)
            except (TypeError, ValueError):
                pass
        polly_characters += billed_chars

        audio_data = response["AudioStream"].read()

        audio_key = f"audio/{video_id}/dvi_{i:03d}.mp3"
        s3.put_object(
            Bucket=bucket, Key=audio_key, Body=audio_data, ContentType="audio/mpeg"
        )

        # Get actual audio duration using mutagen
        try:
            audio_file = MP3(BytesIO(audio_data))
            actual_audio_duration = audio_file.info.length
        except Exception as e:
            print(f"Warning: Could not determine audio duration for segment {i}: {e}")
            actual_audio_duration = None

        audio_files.append({
            "index": i,
            "audio_key": audio_key,
            "start": segment["start"],
            "silence_duration": segment["duration"],
            "actual_audio_duration": actual_audio_duration,
            "text": segment["dvi_text"],
        })

    metadata_key = f"audio/{video_id}/audio-metadata.json"
    s3.put_object(
        Bucket=bucket,
        Key=metadata_key,
        Body=json.dumps({"audio_files": audio_files}, indent=2),
    )

    return {
        "statusCode": 200,
        "video_id": video_id,
        "bucket": bucket,
        "audio_files_generated": len(audio_files),
        "cost_metadata": {"polly_characters": polly_characters},
    }
