"""Detect silence gaps in transcription output suitable for DVI narration.

Silence gaps are derived from Amazon Transcribe's ``audio_segments``: any stretch
of the timeline not covered by a speech segment is a candidate for DVI narration.
We detect three kinds of gaps:

1. Leading silence  - from the start of the video (t=0) to the first speech segment.
2. Internal silence - between two consecutive speech segments.
3. Trailing silence - from the last speech segment to the end of the video.

The leading and trailing gaps matter because intros (logos, establishing shots)
and outros (credits, final imagery) frequently contain no speech yet carry visual
information worth describing. The video's total duration (needed for the trailing
gap) comes from the input metadata written by the validate_input step.
"""
import json

import boto3

s3 = boto3.client("s3")

# Default minimum silence duration (seconds) for DVI narration insertion
DEFAULT_MIN_SILENCE_DURATION = 4.0


def get_video_duration(bucket, video_id):
    """Read total video duration from the validate_input metadata artifact.

    Returns None if the metadata is missing or unreadable, in which case the
    caller skips trailing-silence detection rather than failing the pipeline.
    """
    key = f"metadata/{video_id}/input-metadata.json"
    try:
        obj = s3.get_object(Bucket=bucket, Key=key)
        metadata = json.loads(obj["Body"].read())
        return float(metadata["duration_seconds"])
    except Exception:
        return None


def lambda_handler(event, context):
    bucket = event["bucket"]
    video_id = event["video_id"]
    min_silence_duration = float(event.get("min_silence_duration", DEFAULT_MIN_SILENCE_DURATION))

    key = f"transcribe/{video_id}/transcribe.json"

    obj = s3.get_object(Bucket=bucket, Key=key)
    data = json.loads(obj["Body"].read())

    segments = data["results"]["audio_segments"]
    video_duration = get_video_duration(bucket, video_id)
    silences = []

    def add_gap(gap_start, gap_end):
        duration = gap_end - gap_start
        if duration >= min_silence_duration:
            silences.append(
                {"start": gap_start, "end": gap_end, "duration": duration}
            )

    if not segments:
        # No speech detected at all: the entire video is a silence gap.
        if video_duration is not None:
            add_gap(0.0, video_duration)
    else:
        # Leading silence: start of video to the first speech segment.
        add_gap(0.0, float(segments[0]["start_time"]))

        # Internal silence: gaps between consecutive speech segments.
        for i in range(len(segments) - 1):
            add_gap(float(segments[i]["end_time"]), float(segments[i + 1]["start_time"]))

        # Trailing silence: last speech segment to the end of the video.
        if video_duration is not None:
            add_gap(float(segments[-1]["end_time"]), video_duration)

    output_key = f"transcribe/{video_id}/silences.json"
    s3.put_object(
        Bucket=bucket,
        Key=output_key,
        Body=json.dumps({"silences": silences}, indent=2),
    )

    return {
        "statusCode": 200,
        "video_id": video_id,
        "bucket": bucket,
        "silences_found": len(silences),
    }
