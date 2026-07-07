"""CDK Stack for the DVI processing pipeline infrastructure.

Creates:
- S3 bucket for video storage and processing artifacts
- DynamoDB table for processing summaries
- FFmpeg Lambda layer (built via Docker)
- All pipeline Lambda functions
- Step Functions state machine
"""
import os

from aws_cdk import (
    CfnOutput,
    Duration,
    RemovalPolicy,
    Size,
    Stack,
    aws_dynamodb as dynamodb,
    aws_iam as iam,
    aws_lambda as lambda_,
    aws_s3 as s3,
    aws_stepfunctions as sfn,
    aws_stepfunctions_tasks as tasks,
)
from constructs import Construct

BACKEND_LAMBDAS_DIR = os.path.join(os.path.dirname(__file__), "..", "backend", "lambdas")
FFMPEG_LAYER_DIR = os.path.join(os.path.dirname(__file__), "..", "backend", "layers", "ffmpeg")


class PipelineStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # ======================== S3 BUCKET ========================
        self.bucket = s3.Bucket(
            self,
            "VideoBucket",
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
            cors=[
                s3.CorsRule(
                    allowed_methods=[s3.HttpMethods.PUT, s3.HttpMethods.GET],
                    allowed_origins=["*"],
                    allowed_headers=["*"],
                    max_age=3600,
                )
            ],
        )

        # ======================== DYNAMODB TABLE ========================
        self.table = dynamodb.Table(
            self,
            "SummaryTable",
            partition_key=dynamodb.Attribute(
                name="video_id", type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="execution_id", type=dynamodb.AttributeType.STRING
            ),
            removal_policy=RemovalPolicy.DESTROY,
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
        )

        # ======================== FFMPEG LAMBDA LAYER ========================
        # Built by running: backend/layers/ffmpeg/build-layer.sh
        ffmpeg_layer_path = os.path.join(FFMPEG_LAYER_DIR, "layer")
        if not os.path.isdir(ffmpeg_layer_path):
            raise RuntimeError(
                "FFmpeg layer not built. Run: bash backend/layers/ffmpeg/build-layer.sh"
            )

        self.ffmpeg_layer = lambda_.LayerVersion(
            self,
            "FfmpegLayer",
            description="FFmpeg static binary for video processing",
            code=lambda_.Code.from_asset(ffmpeg_layer_path),
            compatible_runtimes=[lambda_.Runtime.PYTHON_3_12],
            compatible_architectures=[lambda_.Architecture.X86_64],
        )

        # ======================== IAM ROLE (shared) ========================
        lambda_role = iam.Role(
            self,
            "PipelineLambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AWSLambdaBasicExecutionRole"
                ),
            ],
        )

        # S3 access
        self.bucket.grant_read_write(lambda_role)

        # Transcribe access (StartTranscriptionJob does not support resource-level permissions)
        lambda_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "transcribe:StartTranscriptionJob",
                    "transcribe:GetTranscriptionJob",
                ],
                resources=["*"],
            )
        )

        # Bedrock access (scoped to specific model inference profiles)
        lambda_role.add_to_policy(
            iam.PolicyStatement(
                actions=["bedrock:InvokeModel"],
                resources=[
                    f"arn:aws:bedrock:{self.region}:{self.account}:inference-profile/us.twelvelabs.pegasus-1-2-v1:0",
                    f"arn:aws:bedrock:{self.region}:{self.account}:inference-profile/us.anthropic.claude-sonnet-4-5-20250929-v1:0",
                    f"arn:aws:bedrock:*::foundation-model/us.twelvelabs.pegasus-1-2-v1:0",
                    f"arn:aws:bedrock:*::foundation-model/us.anthropic.claude-sonnet-4-5-20250929-v1:0",
                    f"arn:aws:bedrock:*::foundation-model/anthropic.claude-sonnet-4-5-20250929-v1:0",
                    f"arn:aws:bedrock:*::foundation-model/twelvelabs.pegasus-1-2-v1:0",
                ],
            )
        )

        # Polly access
        lambda_role.add_to_policy(
            iam.PolicyStatement(
                actions=["polly:SynthesizeSpeech"],
                resources=["*"],  # Polly does not support resource-level permissions
            )
        )

        # DynamoDB access
        self.table.grant_write_data(lambda_role)

        # ======================== LAMBDA FUNCTIONS ========================
        pegasus_inference_profile_arn = (
            f"arn:aws:bedrock:{self.region}:{self.account}"
            f":inference-profile/us.twelvelabs.pegasus-1-2-v1:0"
        )

        common_env = {
            "BUCKET_NAME": self.bucket.bucket_name,
        }

        # Validation (uses FFmpeg for duration probe)
        self.validate_input_fn = self._create_lambda(
            "ValidateInput", "validate_input", lambda_role, common_env,
            ffmpeg=True, memory=1024, timeout=120,
        )

        # Transcription and silence detection
        self.transcribe_video_fn = self._create_lambda(
            "TranscribeVideo", "transcribe_video", lambda_role, common_env,
            timeout=900,
        )

        self.silence_detection_fn = self._create_lambda(
            "SilenceDetection", "silence_detection", lambda_role, common_env,
        )

        # Segment extraction and analysis
        self.extract_silence_segments_fn = self._create_lambda(
            "ExtractSilenceSegments", "extract_silence_segments", lambda_role,
            {**common_env, "CONTEXT_PAD_BEFORE": "5.0", "CONTEXT_PAD_AFTER": "2.0"},
            ffmpeg=True, memory=3008, timeout=900, ephemeral_storage=10240,
        )

        self.analyze_silence_segment_fn = self._create_lambda(
            "AnalyzeSilenceSegment", "analyze_silence_segment", lambda_role,
            {**common_env, "PEGASUS_MODEL_ID": "us.twelvelabs.pegasus-1-2-v1:0",
             "PEGASUS_INFERENCE_PROFILE_ARN": pegasus_inference_profile_arn},
        )

        # DVI generation and synthesis
        self.generate_dvi_fn = self._create_lambda(
            "GenerateDVI", "generate_dvi", lambda_role,
            {**common_env, "CLAUDE_MODEL_ID": "us.anthropic.claude-sonnet-4-5-20250929-v1:0"},
        )

        self.synthesize_audio_fn = self._create_lambda(
            "SynthesizeAudio", "synthesize_audio", lambda_role, common_env,
            pip_install=True,
        )

        # Final mix and summary
        self.mix_audio_tracks_fn = self._create_lambda(
            "MixAudioTracks", "mix_audio_tracks", lambda_role, common_env,
            ffmpeg=True, memory=3008, timeout=900, ephemeral_storage=10240,
        )

        self.write_summary_dynamodb_fn = self._create_lambda(
            "WriteSummaryDynamoDB", "write_summary_dynamodb", lambda_role,
            {**common_env, "TABLE_NAME": self.table.table_name},
        )

        self.write_summary_s3_fn = self._create_lambda(
            "WriteSummaryS3", "write_summary_s3", lambda_role, common_env,
        )

        # ======================== STEP FUNCTIONS ========================
        sf_role = iam.Role(
            self,
            "StepFunctionsRole",
            assumed_by=iam.ServicePrincipal("states.amazonaws.com"),
        )

        all_lambda_arns = [
            self.validate_input_fn.function_arn,
            self.transcribe_video_fn.function_arn,
            self.silence_detection_fn.function_arn,
            self.extract_silence_segments_fn.function_arn,
            self.analyze_silence_segment_fn.function_arn,
            self.generate_dvi_fn.function_arn,
            self.synthesize_audio_fn.function_arn,
            self.mix_audio_tracks_fn.function_arn,
            self.write_summary_dynamodb_fn.function_arn,
            self.write_summary_s3_fn.function_arn,
        ]
        sf_role.add_to_policy(
            iam.PolicyStatement(
                actions=["lambda:InvokeFunction"],
                resources=all_lambda_arns,
            )
        )

        # Build pipeline chain
        def invoke_step(name, fn):
            return tasks.LambdaInvoke(
                self,
                name,
                lambda_function=fn,
                payload=sfn.TaskInput.from_object({
                    "video_id": sfn.JsonPath.string_at("$.video_id"),
                    "bucket": sfn.JsonPath.string_at("$.bucket"),
                    "min_silence_duration": sfn.JsonPath.number_at("$.min_silence_duration"),
                }),
                result_path=f"$.{name.lower().replace(' ', '_')}_result",
                retry_on_service_exceptions=True,
            )

        # Transcribe uses a wait loop (can take > 15 min for long videos)
        start_transcribe = tasks.LambdaInvoke(
            self,
            "StartTranscribe",
            lambda_function=self.transcribe_video_fn,
            payload=sfn.TaskInput.from_object({
                "video_id": sfn.JsonPath.string_at("$.video_id"),
                "bucket": sfn.JsonPath.string_at("$.bucket"),
            }),
            result_path="$.transcribe",
            result_selector={
                "video_id": sfn.JsonPath.string_at("$.Payload.video_id"),
                "bucket": sfn.JsonPath.string_at("$.Payload.bucket"),
                "job_name": sfn.JsonPath.string_at("$.Payload.transcribe_job_name"),
                "status": sfn.JsonPath.string_at("$.Payload.transcribe_status"),
            },
            retry_on_service_exceptions=True,
        )

        wait_30s = sfn.Wait(
            self, "WaitForTranscribe",
            time=sfn.WaitTime.duration(Duration.seconds(30)),
        )

        check_transcribe = tasks.LambdaInvoke(
            self,
            "CheckTranscribe",
            lambda_function=self.transcribe_video_fn,
            payload=sfn.TaskInput.from_object({
                "video_id": sfn.JsonPath.string_at("$.transcribe.video_id"),
                "bucket": sfn.JsonPath.string_at("$.transcribe.bucket"),
                "transcribe_job_name": sfn.JsonPath.string_at("$.transcribe.job_name"),
            }),
            result_path="$.transcribe",
            result_selector={
                "video_id": sfn.JsonPath.string_at("$.Payload.video_id"),
                "bucket": sfn.JsonPath.string_at("$.Payload.bucket"),
                "job_name": sfn.JsonPath.string_at("$.Payload.transcribe_job_name"),
                "status": sfn.JsonPath.string_at("$.Payload.transcribe_status"),
            },
            retry_on_service_exceptions=True,
        )

        # Post-transcribe pipeline steps
        detect_silences = invoke_step("DetectSilences", self.silence_detection_fn)
        extract_segments = invoke_step("ExtractSegments", self.extract_silence_segments_fn)
        analyze_segments = invoke_step("AnalyzeSegments", self.analyze_silence_segment_fn)
        generate_dvi = invoke_step("GenerateDVI", self.generate_dvi_fn)
        synthesize_audio = invoke_step("SynthesizeAudio", self.synthesize_audio_fn)
        mix_audio = invoke_step("MixAudioTracks", self.mix_audio_tracks_fn)
        write_db = invoke_step("WriteSummaryDB", self.write_summary_dynamodb_fn)
        write_s3 = invoke_step("WriteSummaryS3", self.write_summary_s3_fn)

        # Chain the post-transcribe steps
        post_transcribe = (
            detect_silences
            .next(extract_segments)
            .next(analyze_segments)
            .next(generate_dvi)
            .next(synthesize_audio)
            .next(mix_audio)
            .next(write_db)
            .next(write_s3)
        )

        # Transcribe polling loop
        is_done = sfn.Choice(self, "TranscribeDone")
        is_done.when(
            sfn.Condition.string_equals("$.transcribe.status", "COMPLETED"),
            post_transcribe,
        ).otherwise(wait_30s)

        wait_30s.next(check_transcribe).next(is_done)

        # Full pipeline
        chain = (
            invoke_step("ValidateInput", self.validate_input_fn)
            .next(start_transcribe)
            .next(is_done)
        )

        self.state_machine = sfn.StateMachine(
            self,
            "DviPipeline",
            state_machine_name="dvi-narration-pipeline",
            definition_body=sfn.DefinitionBody.from_chainable(chain),
            role=sf_role,
        )

        # ======================== OUTPUTS ========================
        CfnOutput(self, "BucketName", value=self.bucket.bucket_name)
        CfnOutput(self, "TableName", value=self.table.table_name)
        CfnOutput(self, "StateMachineArn", value=self.state_machine.state_machine_arn)

    def _create_lambda(
        self, id_suffix, lambda_dir, role, environment,
        ffmpeg=False, memory=512, timeout=300, bundling=False,
        ephemeral_storage=None, pip_install=False,
    ):
        """Create a Lambda function with common configuration."""
        layers = [self.ffmpeg_layer] if ffmpeg else []
        lambda_path = os.path.join(BACKEND_LAMBDAS_DIR, lambda_dir)

        if pip_install:
            # Install dependencies locally into the Lambda directory.
            # This works for pure-Python packages (no C extensions).
            import subprocess
            requirements_file = os.path.join(lambda_path, "requirements.txt")
            if os.path.exists(requirements_file):
                # Safe: build-time (cdk synth) dependency install with static args and a
                # repo-controlled requirements path — not runtime, no external/user input.
                subprocess.run(  # nosec B603
                    ["pip", "install", "-r", requirements_file,
                     "-t", lambda_path, "--quiet", "--upgrade"],
                    check=True,
                )

        code = lambda_.Code.from_asset(lambda_path)

        fn = lambda_.Function(
            self,
            f"{id_suffix}Function",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="lambda_function.lambda_handler",
            code=code,
            role=role,
            timeout=Duration.seconds(timeout),
            memory_size=memory,
            layers=layers,
            environment=environment,
            architecture=lambda_.Architecture.X86_64,
            ephemeral_storage_size=Size.mebibytes(ephemeral_storage) if ephemeral_storage else None,
        )

        return fn
