# Backend Lambda Functions

This document explains every Lambda function in the backend: what it does, how it's
configured, the key code decisions, and _why_ those choices were made. It's meant to
be read top-to-bottom as a tour of the pipeline, but each section also stands alone.

There are two groups of functions:

1. **Pipeline Lambdas** (`backend/lambdas/`) — the steps of the Step Functions state
   machine that turns a raw video into a described-video output.
2. **Dashboard / cost Lambdas** (`dashboard/lambdas/`) — the backend-for-frontend that
   powers the web dashboard. This doc covers the **cost calculator** in detail because
   its logic is non-obvious; the other dashboard endpoints are small, single-purpose
   handlers (list videos, presigned URLs, start/poll executions) that follow the same
   request/response pattern.

All pipeline Lambdas are Python 3.12, x86_64, and are created by the shared
`PipelineStack._create_lambda` helper in `infrastructure/pipeline_stack.py`. They
communicate **only through S3 artifacts** — each step reads the previous step's JSON
output from a predictable S3 key and writes its own. The Step Function passes
`video_id`, `bucket`, and `min_silence_duration` between states; everything else flows
through S3. This keeps each Lambda stateless, independently testable, and re-runnable.

---

## Pipeline at a glance

The state machine (`dvi-narration-pipeline`) runs these steps in order:

| #   | Step (SFN state)       | Lambda dir                 | Memory  | Timeout | Layer / extras            |
| --- | ---------------------- | -------------------------- | ------- | ------- | ------------------------- |
| 1   | ValidateInput          | `validate_input`           | 1024 MB | 120 s   | FFmpeg layer              |
| 2   | StartTranscribe + poll | `transcribe_video`         | 512 MB  | 900 s   | —                         |
| 3   | DetectSilences         | `silence_detection`        | 512 MB  | 300 s   | —                         |
| 4   | ExtractSegments        | `extract_silence_segments` | 3008 MB | 900 s   | FFmpeg, 10 GB ephemeral   |
| 5   | AnalyzeSegments        | `analyze_silence_segment`  | 512 MB  | 300 s   | Bedrock (Pegasus)         |
| 6   | GenerateDVI            | `generate_dvi`             | 512 MB  | 300 s   | Bedrock (Claude)          |
| 7   | SynthesizeAudio        | `synthesize_audio`         | 512 MB  | 300 s   | `mutagen` (pip-installed) |
| 8   | MixAudioTracks         | `mix_audio_tracks`         | 3008 MB | 900 s   | FFmpeg, 10 GB ephemeral   |
| 9   | WriteSummaryDB         | `write_summary_dynamodb`   | 512 MB  | 300 s   | —                         |
| 10  | WriteSummaryS3         | `write_summary_s3`         | 512 MB  | 300 s   | —                         |

> Memory/timeout defaults are 512 MB / 300 s. Only steps that deviate are configured
> explicitly — see each section for the reasoning.

---

## 1. `validate_input` — fail fast before spending money

**Config:** 1024 MB, 120 s, FFmpeg layer.
**Reads:** `input/{video_id}.mp4` (the upload).
**Writes:** `metadata/{video_id}/input-metadata.json`.

Validates the upload before the pipeline spends money on Transcribe and Bedrock:

- **File size < 8 GB.** Lambda `/tmp` is capped at 10 GB; later steps download the
  whole video, so we leave headroom.
- **Duration < 8 hours.** This is the Amazon Transcribe hard limit, so we reject early
  with a clear error rather than failing mid-pipeline.

**Key decision — probe duration without downloading the file.** The function generates
a short-lived presigned URL and points FFmpeg at it:

```python
url = s3.generate_presigned_url("get_object", Params={...}, ExpiresIn=300)
cmd = [FFMPEG_PATH, "-i", url, "-f", "null", "-t", "0", "-"]
```

FFmpeg reads only the container header to report `Duration:`, so an 8 GB file is
validated in seconds without a multi-gigabyte download. The duration it extracts is
persisted to `input-metadata.json` and reused downstream (notably by silence detection
for trailing-silence math, and by the cost calculator).

## 2. `transcribe_video` — dual-mode start/poll

**Config:** 512 MB, 900 s.
**Reads:** `input/{video_id}.mp4`.
**Writes:** `transcribe/{video_id}/transcribe.json` (written by Amazon Transcribe).

**Key decision — one Lambda, two modes, driven by Step Functions.** Transcription of a
long video can take far longer than Lambda's 15-minute ceiling, so the Lambda never
_waits_ for the job. Instead:

- **First call** (no `transcribe_job_name` in the event): starts the Transcribe job and
  returns immediately with status `IN_PROGRESS`.
- **Subsequent calls** (job name present): polls `get_transcription_job` and returns the
  current status.

The Step Function owns the wait loop — a `Wait` (30 s) → `CheckTranscribe` → `Choice`
cycle that repeats until status is `COMPLETED`. This keeps the Lambda short-lived and
cheap (you don't pay Lambda compute while waiting) and moves the orchestration where it
belongs.

**Transcribe settings:** `LanguageCode="en-US"`, `ShowSpeakerLabels=True`,
`MaxSpeakerLabels=10`. Speaker labels segment the audio by who's talking, which produces
the `audio_segments` array the next step relies on.

## 3. `silence_detection` — find the gaps, not the silence

**Config:** 512 MB, 300 s (defaults).
**Reads:** `transcribe/{video_id}/transcribe.json`, `metadata/{video_id}/input-metadata.json`.
**Writes:** `transcribe/{video_id}/silences.json`.

**Key decision — detect silence from Transcribe gaps, not audio waveform analysis.**
Rather than running signal processing to find quiet passages, we treat _any stretch of
the timeline not covered by a speech segment_ as a candidate for narration. Amazon
Transcribe already tells us exactly when speech happens via `audio_segments` (each with
`start_time` / `end_time`), so the gaps between/around those segments are precisely the
moments where inserting narration won't talk over dialogue. This is simpler, cheaper, and
directly aligned with the goal: we want to narrate _when no one is speaking_.

A gap qualifies as a usable silence when it's at least `min_silence_duration` seconds.
That threshold comes from the Step Function execution input
(`event["min_silence_duration"]`, which the dashboard's Trigger page exposes) and falls
back to `DEFAULT_MIN_SILENCE_DURATION = 4.0` when not supplied — short enough to be
common, long enough to fit a useful spoken description.

We detect **three** kinds of gap so we don't miss content at the edges of the video:

```python
# Leading silence: start of video to the first speech segment
add_gap(0.0, float(segments[0]["start_time"]))

# Internal silence: between consecutive speech segments
for i in range(len(segments) - 1):
    add_gap(float(segments[i]["end_time"]), float(segments[i + 1]["start_time"]))

# Trailing silence: last speech segment to the end of the video
add_gap(float(segments[-1]["end_time"]), video_duration)
```

- **Leading silence** covers intros — logos, establishing shots, title cards — that play
  before anyone speaks.
- **Internal silence** is the obvious case: pauses between lines of dialogue.
- **Trailing silence** covers outros and closing credits. It needs the video's total
  duration, which we read from `input-metadata.json` (written by `validate_input`). The
  duration read is guarded — if the metadata is missing, we skip the trailing gap rather
  than fail the run.

A fully silent video (no `audio_segments` at all) is treated as one big gap from `0` to
the video duration.

> Why this matters: an earlier version only looked at gaps _between_ consecutive
> segments, so any silence before the first word or after the last word was invisible to
> the pipeline. Edge narration (intros/outros) was silently dropped.

## 4. `extract_silence_segments` — give the vision model context

**Config:** 3008 MB, 900 s, FFmpeg layer, **10 GB ephemeral storage**.
**Reads:** `input/{video_id}.mp4`, `transcribe/{video_id}/silences.json`.
**Writes:** `silence-segments/{video_id}/segment_NNN.mp4` + `segments-metadata.json`.

Extracts one short video clip per silence gap so the vision model has something to look
at. The high memory + 10 GB ephemeral storage exist because this step downloads the full
source video to `/tmp` and runs FFmpeg on it; Lambda CPU scales with memory, so 3008 MB
keeps the re-encode fast.

**Key decision — pad each clip with surrounding context.** A silence gap on its own is
often just a static or transitional moment. To let the model describe _what's happening_,
we extend each clip with `CONTEXT_PAD_BEFORE = 5.0` s and `CONTEXT_PAD_AFTER = 2.0` s
(both env-overridable) around the gap:

```python
extract_start = max(0, start - CONTEXT_PAD_BEFORE)
extract_end   = min(video_duration, end + CONTEXT_PAD_AFTER)
```

The `max(0, …)` / `min(video_duration, …)` clamps are what make leading silence
(`start = 0`) and trailing silence (`end = duration`) safe to extract — they can't run
off either end of the video. Set both pads to `0` for silence-only clips.

There's also a `MIN_PEGASUS_DURATION = 4.0` s floor: Pegasus rejects clips shorter than
4 seconds, so if padding still isn't enough the code extends the window symmetrically to
reach the minimum. FFmpeg uses `libx264 -preset ultrafast` because these are throwaway
analysis clips — encode speed matters, visual quality doesn't.

## 5. `analyze_silence_segment` — describe what's on screen (Pegasus)

**Config:** 512 MB, 300 s. Env: `PEGASUS_MODEL_ID`, `PEGASUS_INFERENCE_PROFILE_ARN`.
**Reads:** `silence-segments/{video_id}/segments-metadata.json` + the clips.
**Writes:** `analyses/{video_id}/segment-analyses.json`.

Sends each clip to **Twelve Labs Pegasus 1.2** (a video-understanding model) via Bedrock
and stores a plain-language description of the visuals.

**Key decision — the Bedrock client needs an inference-profile header.** Pegasus is
invoked through a Bedrock inference profile, which requires a custom header that the
standard SDK call doesn't set. The function registers an event hook to inject it:

```python
client.meta.events.register(
    "before-call.bedrock-runtime.InvokeModel",
    lambda params, **kwargs: params["headers"].update(
        {"X-Amzn-Bedrock-Inference-Profile-Arn": INFERENCE_PROFILE_ARN}
    ),
)
```

**Key decision — the prompt is constrained to accessibility rules.** The prompt tells the
model to describe only what is _visually observable_ — actions, settings, on-screen text,
meaningful body language — and explicitly **not** to infer motivations or meaning. That
restraint is a core audio-description principle (describe, don't interpret) and it starts
here, at the analysis step. `temperature=0.2` keeps descriptions factual and repeatable.
Clips below `MIN_SEGMENT_DURATION = 1.0` s are skipped with a placeholder rather than sent
to the model. Per-segment errors are caught and recorded so one bad clip doesn't fail the
whole run.

**Cost reporting (additive).** The step now emits an additive `cost_metadata` block in
its return value for the cost dashboard:
`{"pegasus_video_seconds": <sum of analyzed clip durations>, "bedrock_input_tokens": <sum>, "bedrock_output_tokens": <sum>}`.
Pegasus **input is billed per second of video** (not per token), so `pegasus_video_seconds`
— summed over the segments actually submitted (too-short skipped segments contribute 0) —
is the billable input quantity; output is billed per token. This is purely additive: it
does not change the `segment-analyses.json` artifact or any other return field.

## 6. `generate_dvi` — turn analysis into narration (Claude)

**Config:** 512 MB, 300 s. Env: `CLAUDE_MODEL_ID`.
**Reads:** `transcribe/{video_id}/silences.json`, `analyses/{video_id}/segment-analyses.json`.
**Writes:** `dvi/{video_id}/dvi-segments.json`.

Converts each raw visual analysis into a concise spoken-narration script using **Claude
Sonnet 4.5**. It matches an analysis to its silence by timestamp
(`abs(a["start_time"] - silence["start"]) < 0.01`).

**Key decision — budget the words to the available silence.** Narration has to fit inside
the gap or it will collide with dialogue. The prompt caps length based on the gap
duration at a natural speaking rate (~150 wpm):

```python
Maximum {int(silence['duration'] * 2.5)} words
```

The prompt encodes two tiers of audio-description guidance.

**Core rules (always enforced).** Accessibility-standard style rules referencing
FCC / CRTC / WCAG 2.1 SC 1.2.5:

- Describe only what is seen — never interpret motivations, emotions, or meaning
- Present tense, third person
- Objective, simple, succinct
- Prioritize information essential for comprehension
- Match the tone and style of the content
- A hard word cap of `int(silence['duration'] * 2.5)` words (~150 wpm) so the narration
  fits the gap
- One flowing sentence or two short ones, no bullet points
- No "We see…" / "The screen shows…" openers

**Complementary guidance (applied only when it fits).** A second block
(`COMPLEMENTARY_GUIDANCE`, a module-level constant) refines the core rules with
craft-level conventions paraphrased from widely used industry AD style guidance (the same
principles appear in broadcaster/streamer style guides and ACB/ADP and Ofcom guidance):

- **Accuracy over detail** — if the analysis doesn't clearly establish something, use a
  general term instead of guessing ("herbs," not a specific herb) and never invent details
  the analysis doesn't support. (This is also our main anti-hallucination lever, since the
  upstream Pegasus analysis can be uncertain.)
- **People** — describe observable attributes (approximate age, build, hair, clothing);
  don't assume race, ethnicity, or gender the analysis hasn't established; describe
  comparable characters with comparable detail; use person-first wording ("a swimmer with
  one leg").
- **Expressions** — convey facial expressions and body language through the _visible cue_
  (a furrowed brow, clenched fists), not by naming the emotion; omit when they merely
  restate the obvious.
- **Verbs** — prefer one vivid verb over a weak verb plus an adverb ("hobbles" vs "walks
  with difficulty") — sharper _and_ shorter.
- **Pronouns** — only when the referent is unambiguous.
- **Direction** — relative to the viewer ("to the left of the doorway") when it matters.
- **Setting/time/weather** — only when meaningful to the scene.
- **No censorship** — describe sensitive content plainly and factually, with audience-
  appropriate word choice.

**Why two tiers — and why the complementary block is subordinate.** The two sets are
designed not to contradict each other. The one potential clash — "describe expressions"
vs. the core "never interpret emotions" — is resolved by phrasing the complementary point
as _describe the visible cue, not the named emotion_, which reinforces the core rule. The
block is explicitly gated ("apply only when it fits within the word limit and after the
most essential information is covered"), so the word budget and prioritization always win
when space is tight. The guidance is **paraphrased in our own words**, not copied from any
single proprietary style guide, so the sample stays freely distributable.

**Not yet covered (would need pipeline changes).** Cross-segment consistency (a shared
character/location glossary, naming a character once introduced and staying consistent
across segments) can't be honored by this stateless, per-segment step — it would require
passing video-level context between segments. See the README "Full-Video Context" note.

`temperature=0.3` and `max_tokens=200` keep output tight and consistent.

**Cost reporting (additive).** The step now emits an additive `cost_metadata` block
`{"bedrock_input_tokens": <sum>, "bedrock_output_tokens": <sum>}`, summed from each Claude
invocation's `result["usage"]` (errored invocations contribute 0), and consumed by the
cost dashboard. Additive only — no change to `dvi-segments.json`.

## 7. `synthesize_audio` — text to speech (Polly)

**Config:** 512 MB, 300 s. Built with `pip_install=True` (bundles `mutagen`).
**Reads:** `dvi/{video_id}/dvi-segments.json`.
**Writes:** `audio/{video_id}/dvi_NNN.mp3` + `audio-metadata.json`.

Synthesizes each narration line to MP3 with **Amazon Polly** (`VoiceId="Matthew"`,
`Engine="neural"` for natural prosody).

**Key decision — measure the real audio length with `mutagen`.** Polly returns audio but
not its duration, and we need to know whether each clip actually fits its silence gap. The
function reads the MP3 with `mutagen` to get the true length and records it in
`audio-metadata.json`, which the summary step later uses for a PASS/FAIL fit check.
`mutagen` is pure Python, so the stack installs it directly into the function directory at
synth time (`pip_install=True`) rather than building a layer.

**Cost reporting (additive).** The step now emits an additive `cost_metadata` block
`{"polly_characters": <sum>}` — billed characters equal the sum of `len(dvi_text)` across
segments (synthesis uses `TextType="text"`, optionally cross-checked against the
`x-amzn-RequestCharacters` response header). Additive only.

## 8. `mix_audio_tracks` — overlay narration onto the video (FFmpeg)

**Config:** 3008 MB, 900 s, FFmpeg layer, **10 GB ephemeral storage**.
**Reads:** `input/{video_id}.mp4`, `audio/{video_id}/audio-metadata.json` + the MP3s.
**Writes:** `final/{video_id}-{timestamp}.mp4`.

Downloads the original video and every narration clip, then uses an FFmpeg
`filter_complex` to delay each narration clip to its timestamp and mix it onto the
original audio track.

**Key decision — `adelay` + `amix` with `normalize=0`.** Each narration track is delayed
to its start time and the original audio is mixed in with normalization **off**:

```python
f"[{i+1}:a]adelay={delay_ms}|{delay_ms},volume=1.5[a{i}]"   # per clip
f"{inputs}amix=inputs=N:duration=longest:normalize=0[aout]"  # final mix
```

`normalize=0` is deliberate: `amix` normally lowers the volume of all inputs to avoid
clipping, which would duck the original soundtrack every time narration plays. Turning it
off (with a slight `volume=1.5` boost on narration) keeps the original audio at full level
and the narration clearly audible. The video stream is copied (`-c:v copy`) — only audio is
re-encoded — so mixing is fast and lossless for the picture. If there's no narration at
all, the original is copied through unchanged.

## 9. `write_summary_dynamodb` — structured record + fit check

**Config:** 512 MB, 300 s. Env: `TABLE_NAME`.
**Reads:** `silences.json`, `dvi-segments.json`, `audio-metadata.json`.
**Writes:** one item to DynamoDB (keys `video_id` + `execution_id`).

Persists a structured per-execution summary. Floats are converted to `Decimal` because
DynamoDB rejects native floats. **Key detail — the PASS/FAIL fit check:** for each
segment it compares the actual synthesized audio duration against the silence duration and
flags `FAIL` when narration is longer than the gap, then totals passed/failed segments.
This is the pipeline's built-in quality signal for "did the narration actually fit?".

## 10. `write_summary_s3` — human-readable summary

**Config:** 512 MB, 300 s.
**Reads:** `dvi/{video_id}/dvi-segments.json`.
**Writes:** `summaries/{video_id}-summary-{shortid}.txt`.

Writes a plain-text report (timestamps formatted `HH:MM:SS.mmm`, each segment's silence
window and narration text) for quick human review without querying DynamoDB or parsing
JSON. The summary-building logic is split into a pure `build_summary_text()` function,
which makes it straightforward to unit-test.

---

## Cost calculator (`dashboard/lambdas/calculate_cost`)

**Config:** Python 3.12, 256 MB, 60 s (dashboard Lambdas are 30 s; this one gets 60 s
because it paginates through execution history). Env: `STATE_MACHINE_ARN`.

Given a Step Functions execution ARN, it reconstructs an estimated cost breakdown. It does
**not** call AWS Cost Explorer (which is account-aggregated and delayed); instead it
derives per-execution cost from the execution's own history.

**How it works:**

1. **Walk the execution history.** It pages through `get_execution_history` and pairs
   `TaskStateEntered` / `TaskStateExited` events to get a duration and output payload per
   step.
2. **Step Functions cost** = number of state transitions × per-transition price.
3. **Lambda cost** per step = `request + (memory_GB × duration_s × per-GB-second)`. Memory
   is looked up live via `get_function_configuration` (falling back to 512 MB).
4. **Downstream service cost** (Transcribe, Bedrock, Polly, DynamoDB, S3) is read from a
   `cost_metadata` block in each step's output **when present**, and falls back to
   duration-based estimates otherwise. To find each step's output, the estimator maps each
   in-scope deployed state to the `invoke_step` result-path convention
   (`state_name.lower().replace(' ', '_') + "_result"`) — `ValidateInput →
validateinput_result`, `AnalyzeSegments → analyzesegments_result`, `GenerateDVI →
generatedvi_result`, `SynthesizeAudio → synthesizeaudio_result` — and reads
   `cost_metadata` from each step's `Payload`. Prices live in a single `PRICING` table
   (us-east-1) so they're easy to update.

**Per-service sourcing:**

- **Transcribe** is sourced from `ValidateInput`'s `duration_seconds` (the Transcribe
  states' `result_selector` strips usage) at $0.00040/sec.
- **Pegasus** input is priced per video-second ($0.00049) and output per 1k tokens
  ($0.0075 = $7.50/1M).
- **Claude** is priced from tokens (input + output).
- **Polly** is priced at the **neural** rate ($0.000016/char).

**Graceful degradation:** when usage data is genuinely absent, line items are labeled
`(estimated)` (Transcribe/Pegasus, duration-based) or `(usage unavailable)`
(Claude/Polly) rather than reporting a silent `$0`.

**Why estimates, not exact billing:** real per-request billing isn't available at
execution time, and waiting for Cost Explorer would make the dashboard's cost page useless
for "what did this run just cost me?". The metadata-first / estimate-fallback design gives
an immediate, reasonably accurate number that gets more precise as steps emit
`cost_metadata`.

> **Maintenance note:** the in-scope deployed states (`ValidateInput`, `AnalyzeSegments`,
> `GenerateDVI`, `SynthesizeAudio`) are now correctly mapped to the deployed `invoke_step`
> result-path convention, so `cost_metadata` is read from the right payload for each. The
> legacy `V1/V2/V3` state-to-function maps remain only for backward compatibility with
> older executions recorded under the earlier multi-pipeline layout; they're harmless for
> current runs and the estimator still falls back to duration-based estimates for any state
> it can't map.
