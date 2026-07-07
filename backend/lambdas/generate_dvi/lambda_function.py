"""Generate DVI narration text from visual segment analyses using Claude."""
import json
import os

import boto3

s3 = boto3.client("s3")
CLAUDE_MODEL_ID = os.environ.get(
    "CLAUDE_MODEL_ID", "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
)
REGION = os.environ.get("AWS_REGION", "us-east-1")
bedrock = boto3.client("bedrock-runtime", region_name=REGION)

# Complementary audio-description guidance, paraphrased in our own words from
# widely used industry AD style guidance (broadcaster/streamer style guides; the
# same principles appear in ACB/ADP and Ofcom guidance). These REFINE the core
# rules in the prompt and are deliberately subordinate to them: the word budget
# and "cover the essential first" rule always win when space is tight. Nothing
# here should contradict the core rules (e.g., we describe a *visible* expression
# rather than naming an emotion, which keeps the "no interpretation" rule intact).
COMPLEMENTARY_GUIDANCE = """\
Additional guidance — apply only when it fits within the word limit and after the most essential information is covered:
- Accuracy over detail: if the visual analysis does not clearly establish something, use a general term rather than guess (e.g., "herbs," not a specific herb), and never invent details the analysis does not support.
- Describe people by observable attributes (approximate age, build, hair, clothing) when relevant; do not assume or state race, ethnicity, or gender the analysis has not established. Give comparable characters comparable detail, and use person-first wording (e.g., "a swimmer with one leg").
- Convey meaningful facial expressions and body language through what is visible (a furrowed brow, clenched fists) rather than by naming the emotion; omit them when they merely repeat what is already obvious.
- Prefer one precise, vivid verb over a weak verb plus an adverb (e.g., "hobbles" rather than "walks with difficulty").
- Use a pronoun only when its referent is unambiguous; otherwise name the subject briefly.
- Give direction relative to the viewer when it matters (e.g., "to the left of the doorway").
- Mention setting, time of day, or weather only when meaningful to the scene.
- Do not censor: describe sensitive content (violence, intimacy) plainly and factually, with word choice appropriate to the audience."""


def lambda_handler(event, context):
    video_id = event["video_id"]
    bucket = event["bucket"]

    # Get silences
    silence_key = f"transcribe/{video_id}/silences.json"
    silence_obj = s3.get_object(Bucket=bucket, Key=silence_key)
    silences = json.loads(silence_obj["Body"].read())["silences"]

    # Get segment analyses
    analyses_key = f"analyses/{video_id}/segment-analyses.json"
    analyses_obj = s3.get_object(Bucket=bucket, Key=analyses_key)
    segment_analyses = json.loads(analyses_obj["Body"].read())["segment_analyses"]

    dvi_segments = []
    bedrock_input_tokens = 0
    bedrock_output_tokens = 0

    for silence in silences:
        analysis = next(
            (
                a
                for a in segment_analyses
                if abs(a["start_time"] - silence["start"]) < 0.01
            ),
            None,
        )

        if not analysis:
            continue

        prompt = f"""You are writing audio description (AD) narration for a video, following international accessibility standards (FCC, CRTC/Canadian Audio Description Guidelines, WCAG 2.1 SC 1.2.5).

Visual analysis of this segment:
{analysis['analysis']}

Timestamp: {silence['start']:.1f} seconds
Available silence duration: {silence['duration']:.1f} seconds

Write the audio description narration following these rules:
- Describe only what is seen — never interpret motivations, emotions, or meaning
- Use present tense, third person
- Be objective, simple, and succinct
- Prioritize information essential for comprehension
- Match the tone and style of the content
- Maximum {int(silence['duration'] * 2.5)} words (narration at natural conversational pace of ~150 words per minute)
- Write a single flowing sentence or two short sentences — no bullet points
- Do not start with "We see" or "The screen shows"

{COMPLEMENTARY_GUIDANCE}

Narration:"""

        request_body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 200,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3,
        }

        try:
            response = bedrock.invoke_model(
                modelId=CLAUDE_MODEL_ID,
                contentType="application/json",
                accept="application/json",
                body=json.dumps(request_body),
            )
            result = json.loads(response["body"].read().decode())
            dvi_text = result["content"][0]["text"].strip()
            # Accumulate Bedrock (Claude) token usage for cost reporting.
            # Errored invocations skip this block and contribute 0.
            usage = result.get("usage", {})
            bedrock_input_tokens += usage.get("input_tokens", 0)
            bedrock_output_tokens += usage.get("output_tokens", 0)
        except Exception as e:
            dvi_text = f"Error: {e}"

        dvi_segments.append({
            "start": silence["start"],
            "end": silence["end"],
            "duration": silence["duration"],
            "dvi_text": dvi_text,
        })

    output_key = f"dvi/{video_id}/dvi-segments.json"
    s3.put_object(
        Bucket=bucket,
        Key=output_key,
        Body=json.dumps({"segments": dvi_segments}, indent=2),
    )

    return {
        "statusCode": 200,
        "video_id": video_id,
        "bucket": bucket,
        "dvi_segments": len(dvi_segments),
        "cost_metadata": {
            "bedrock_input_tokens": bedrock_input_tokens,
            "bedrock_output_tokens": bedrock_output_tokens,
        },
    }
