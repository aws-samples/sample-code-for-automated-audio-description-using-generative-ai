"""Start or check transcription of video audio using Amazon Transcribe.

This Lambda handles two modes:
- Start: Kicks off a Transcribe job and returns immediately
- Check: Polls the job status and returns it

Step Functions orchestrates the wait loop between calls.
"""
import os
import uuid

import boto3

REGION = os.environ.get("AWS_REGION", "us-east-1")
transcribe = boto3.client("transcribe", region_name=REGION)


def lambda_handler(event, context):
    video_id = event["video_id"]
    bucket = event["bucket"]

    # If we already started a job, check its status
    job_name = event.get("transcribe_job_name")
    if job_name:
        status = transcribe.get_transcription_job(TranscriptionJobName=job_name)
        job_status = status["TranscriptionJob"]["TranscriptionJobStatus"]

        if job_status == "FAILED":
            failure_reason = status["TranscriptionJob"].get("FailureReason", "Unknown")
            raise Exception(f"Transcription failed: {failure_reason}")

        return {
            "video_id": video_id,
            "bucket": bucket,
            "transcribe_job_name": job_name,
            "transcribe_status": job_status,
            "transcribe_output": f"s3://{bucket}/transcribe/{video_id}/transcribe.json",
        }

    # First call — start the job
    short_id = uuid.uuid4().hex[:8]
    job_name = f"{video_id}-transcribe-{short_id}"
    media_uri = f"s3://{bucket}/input/{video_id}.mp4"

    transcribe.start_transcription_job(
        TranscriptionJobName=job_name,
        Media={"MediaFileUri": media_uri},
        MediaFormat="mp4",
        LanguageCode="en-US",
        OutputBucketName=bucket,
        OutputKey=f"transcribe/{video_id}/transcribe.json",
        Settings={"ShowSpeakerLabels": True, "MaxSpeakerLabels": 10},
    )

    return {
        "video_id": video_id,
        "bucket": bucket,
        "transcribe_job_name": job_name,
        "transcribe_status": "IN_PROGRESS",
        "transcribe_output": f"s3://{bucket}/transcribe/{video_id}/transcribe.json",
    }
