"""CDK Stack for the DVI Dashboard (web app + API).

Creates:
- Cognito User Pool for authentication (with auto-created admin user)
- API Gateway REST API with Cognito authorizer
- CloudFront distribution serving React frontend + API
- S3 bucket for frontend hosting
"""
import json
import os

from aws_cdk import (
    CfnOutput,
    Duration,
    RemovalPolicy,
    Stack,
    aws_apigateway as apigateway,
    aws_cloudfront as cloudfront,
    aws_cloudfront_origins as origins,
    aws_cognito as cognito,
    aws_iam as iam,
    aws_lambda as lambda_,
    aws_s3 as s3,
    aws_s3_deployment as s3_deployment,
    custom_resources as cr,
)
from constructs import Construct

DASHBOARD_LAMBDAS_DIR = os.path.join(os.path.dirname(__file__), "..", "dashboard", "lambdas")
FRONTEND_DIST_DIR = os.path.join(os.path.dirname(__file__), "..", "dashboard", "frontend", "dist")


class DashboardStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        pipeline_bucket_name: str,
        pipeline_table_name: str,
        state_machine_arn: str,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # ======================== COGNITO AUTHENTICATION ========================
        self.user_pool = cognito.UserPool(
            self,
            "DviUserPool",
            user_pool_name="dvi-dashboard-users",
            self_sign_up_enabled=False,
            sign_in_aliases=cognito.SignInAliases(email=True),
            auto_verify=cognito.AutoVerifiedAttrs(email=True),
            password_policy=cognito.PasswordPolicy(
                min_length=8,
                require_lowercase=True,
                require_uppercase=True,
                require_digits=True,
                require_symbols=False,
            ),
            removal_policy=RemovalPolicy.DESTROY,
        )

        self.user_pool_client = self.user_pool.add_client(
            "DviWebClient",
            user_pool_client_name="dvi-dashboard-web",
            auth_flows=cognito.AuthFlow(user_srp=True),
            prevent_user_existence_errors=True,
        )

        # Auto-create admin user if email provided at deploy time
        admin_email = self.node.try_get_context("adminEmail")
        if admin_email:
            cr.AwsCustomResource(
                self,
                "CreateAdminUser",
                on_create=cr.AwsSdkCall(
                    service="CognitoIdentityServiceProvider",
                    action="adminCreateUser",
                    parameters={
                        "UserPoolId": self.user_pool.user_pool_id,
                        "Username": admin_email,
                        "UserAttributes": [
                            {"Name": "email", "Value": admin_email},
                            {"Name": "email_verified", "Value": "true"},
                        ],
                        "DesiredDeliveryMediums": ["EMAIL"],
                    },
                    physical_resource_id=cr.PhysicalResourceId.of(f"admin-user-{admin_email}"),
                    ignore_error_codes_matching="UsernameExistsException",
                ),
                policy=cr.AwsCustomResourcePolicy.from_statements([
                    iam.PolicyStatement(
                        actions=["cognito-idp:AdminCreateUser"],
                        resources=[self.user_pool.user_pool_arn],
                    )
                ]),
            )

        # ======================== S3 HOSTING BUCKET ========================
        self.hosting_bucket = s3.Bucket(
            self,
            "DashboardHosting",
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
        )

        # ======================== LAMBDA FUNCTIONS ========================
        common_env = {
            "BUCKET_NAME": pipeline_bucket_name,
            "TABLE_NAME": pipeline_table_name,
        }

        trigger_env = {
            **common_env,
            "STATE_MACHINE_ARN": state_machine_arn,
        }

        # Viewer page lambdas
        self.list_videos_fn = self._create_lambda("ListVideos", "list_videos", common_env)
        self.get_video_url_fn = self._create_lambda("GetVideoUrl", "get_video_url", common_env)
        self.get_segments_fn = self._create_lambda("GetSegments", "get_segments", common_env)
        self.get_summary_fn = self._create_lambda("GetSummary", "get_summary", common_env)

        # Trigger page lambdas
        self.list_input_videos_fn = self._create_lambda("ListInputVideos", "list_input_videos", common_env)
        self.get_input_video_url_fn = self._create_lambda("GetInputVideoUrl", "get_input_video_url", common_env)
        self.upload_video_fn = self._create_lambda("UploadVideo", "upload_video", common_env)
        self.start_execution_fn = self._create_lambda("StartExecution", "start_execution", trigger_env)
        self.get_execution_status_fn = self._create_lambda("GetExecutionStatus", "get_execution_status", trigger_env)

        # Cost page lambdas
        self.list_executions_fn = self._create_lambda("ListExecutions", "list_executions", trigger_env)
        self.calculate_cost_fn = self._create_lambda(
            "CalculateCost", "calculate_cost", trigger_env, timeout=60,
        )

        # ======================== IAM PERMISSIONS ========================
        pipeline_bucket_arn = f"arn:aws:s3:::{pipeline_bucket_name}"

        # S3 permissions
        for fn in [self.list_videos_fn, self.list_input_videos_fn]:
            fn.add_to_role_policy(iam.PolicyStatement(
                actions=["s3:ListBucket"],
                resources=[pipeline_bucket_arn],
            ))

        for fn in [self.get_video_url_fn, self.get_input_video_url_fn, self.get_segments_fn]:
            fn.add_to_role_policy(iam.PolicyStatement(
                actions=["s3:GetObject"],
                resources=[f"{pipeline_bucket_arn}/*"],
            ))

        # Upload permission (presigned PUT URL)
        self.upload_video_fn.add_to_role_policy(iam.PolicyStatement(
            actions=["s3:PutObject"],
            resources=[f"{pipeline_bucket_arn}/input/*"],
        ))

        # DynamoDB permissions
        self.get_summary_fn.add_to_role_policy(iam.PolicyStatement(
            actions=["dynamodb:GetItem", "dynamodb:Query"],
            resources=[f"arn:aws:dynamodb:{self.region}:{self.account}:table/{pipeline_table_name}"],
        ))

        # Step Functions permissions
        self.start_execution_fn.add_to_role_policy(iam.PolicyStatement(
            actions=["states:StartExecution"],
            resources=[state_machine_arn],
        ))

        for fn in [self.get_execution_status_fn, self.calculate_cost_fn]:
            fn.add_to_role_policy(iam.PolicyStatement(
                actions=["states:DescribeExecution", "states:GetExecutionHistory"],
                resources=[f"arn:aws:states:{self.region}:{self.account}:execution:*"],
            ))

        self.list_executions_fn.add_to_role_policy(iam.PolicyStatement(
            actions=["states:ListExecutions"],
            resources=[state_machine_arn],
        ))

        self.calculate_cost_fn.add_to_role_policy(iam.PolicyStatement(
            actions=["lambda:GetFunctionConfiguration"],
            resources=[f"arn:aws:lambda:{self.region}:{self.account}:function:*"],
        ))

        # ======================== API GATEWAY ========================
        api = apigateway.RestApi(
            self,
            "DviDashboardApi",
            rest_api_name="DVI Dashboard API",
            deploy_options=apigateway.StageOptions(stage_name="prod"),
            default_cors_preflight_options=apigateway.CorsOptions(
                allow_origins=apigateway.Cors.ALL_ORIGINS,
                allow_methods=apigateway.Cors.ALL_METHODS,
                allow_headers=["Content-Type", "Authorization"],
            ),
        )

        # Cognito authorizer for all API endpoints
        authorizer = apigateway.CognitoUserPoolsAuthorizer(
            self,
            "DviCognitoAuthorizer",
            cognito_user_pools=[self.user_pool],
        )

        method_options = {
            "authorization_type": apigateway.AuthorizationType.COGNITO,
            "authorizer": authorizer,
        }

        api_resource = api.root.add_resource("api")

        # /api/videos
        videos = api_resource.add_resource("videos")
        videos.add_method("GET", apigateway.LambdaIntegration(self.list_videos_fn, proxy=True), **method_options)

        video_param = videos.add_resource("{id}")
        video_param.add_resource("url").add_method("GET", apigateway.LambdaIntegration(self.get_video_url_fn, proxy=True), **method_options)
        video_param.add_resource("segments").add_method("GET", apigateway.LambdaIntegration(self.get_segments_fn, proxy=True), **method_options)
        video_param.add_resource("summary").add_method("GET", apigateway.LambdaIntegration(self.get_summary_fn, proxy=True), **method_options)

        # /api/trigger
        trigger = api_resource.add_resource("trigger")
        trigger_videos = trigger.add_resource("videos")
        trigger_videos.add_method("GET", apigateway.LambdaIntegration(self.list_input_videos_fn, proxy=True), **method_options)

        trigger_upload = trigger.add_resource("upload")
        trigger_upload.add_method("POST", apigateway.LambdaIntegration(self.upload_video_fn, proxy=True), **method_options)

        trigger_video_param = trigger_videos.add_resource("{video_id}")
        trigger_video_param.add_resource("url").add_method("GET", apigateway.LambdaIntegration(self.get_input_video_url_fn, proxy=True), **method_options)

        trigger_executions = trigger.add_resource("executions")
        trigger_executions.add_method("POST", apigateway.LambdaIntegration(self.start_execution_fn, proxy=True), **method_options)

        trigger_exec_param = trigger_executions.add_resource("{arn}")
        trigger_exec_param.add_resource("status").add_method("GET", apigateway.LambdaIntegration(self.get_execution_status_fn, proxy=True), **method_options)

        # /api/cost
        cost = api_resource.add_resource("cost")
        cost_executions = cost.add_resource("executions")
        cost_executions.add_method("GET", apigateway.LambdaIntegration(self.list_executions_fn, proxy=True), **method_options)

        cost_exec_param = cost_executions.add_resource("{arn}")
        cost_exec_param.add_resource("cost").add_method("GET", apigateway.LambdaIntegration(self.calculate_cost_fn, proxy=True), **method_options)

        # ======================== CLOUDFRONT ========================
        self.distribution = cloudfront.Distribution(
            self,
            "DashboardCDN",
            default_behavior=cloudfront.BehaviorOptions(
                origin=origins.S3BucketOrigin.with_origin_access_control(self.hosting_bucket),
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                response_headers_policy=cloudfront.ResponseHeadersPolicy(
                    self,
                    "SecurityHeaders",
                    security_headers_behavior=cloudfront.ResponseSecurityHeadersBehavior(
                        content_type_options=cloudfront.ResponseHeadersContentTypeOptions(override=True),
                        frame_options=cloudfront.ResponseHeadersFrameOptions(
                            frame_option=cloudfront.HeadersFrameOption.DENY, override=True
                        ),
                        referrer_policy=cloudfront.ResponseHeadersReferrerPolicy(
                            referrer_policy=cloudfront.HeadersReferrerPolicy.STRICT_ORIGIN_WHEN_CROSS_ORIGIN,
                            override=True,
                        ),
                        strict_transport_security=cloudfront.ResponseHeadersStrictTransportSecurity(
                            access_control_max_age=Duration.seconds(63072000),
                            include_subdomains=True,
                            override=True,
                        ),
                    ),
                ),
            ),
            additional_behaviors={
                "/api/*": cloudfront.BehaviorOptions(
                    origin=origins.RestApiOrigin(api),
                    allowed_methods=cloudfront.AllowedMethods.ALLOW_ALL,
                    cache_policy=cloudfront.CachePolicy.CACHING_DISABLED,
                    viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                    origin_request_policy=cloudfront.OriginRequestPolicy.ALL_VIEWER_EXCEPT_HOST_HEADER,
                ),
            },
            default_root_object="index.html",
            error_responses=[
                cloudfront.ErrorResponse(http_status=403, response_page_path="/index.html", response_http_status=200),
                cloudfront.ErrorResponse(http_status=404, response_page_path="/index.html", response_http_status=200),
            ],
        )

        # Deploy frontend and auth config together
        # Auth config is generated at deploy time with Cognito details
        auth_config_content = json.dumps({
            "userPoolId": self.user_pool.user_pool_id,
            "userPoolClientId": self.user_pool_client.user_pool_client_id,
            "region": self.region,
        })
        s3_deployment.BucketDeployment(
            self,
            "DeployFrontend",
            sources=[
                s3_deployment.Source.asset(FRONTEND_DIST_DIR),
                s3_deployment.Source.data("auth-config.json", auth_config_content),
            ],
            destination_bucket=self.hosting_bucket,
            distribution=self.distribution,
            distribution_paths=["/*"],
        )

        # ======================== OUTPUTS ========================
        CfnOutput(self, "DashboardURL", value=f"https://{self.distribution.distribution_domain_name}")
        CfnOutput(self, "ApiURL", value=api.url)
        CfnOutput(self, "UserPoolId", value=self.user_pool.user_pool_id)
        CfnOutput(self, "UserPoolClientId", value=self.user_pool_client.user_pool_client_id)

    def _create_lambda(self, id_suffix, lambda_dir, environment, timeout=30):
        """Create a dashboard Lambda function."""
        return lambda_.Function(
            self,
            f"{id_suffix}Function",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="lambda_function.lambda_handler",
            code=lambda_.Code.from_asset(os.path.join(DASHBOARD_LAMBDAS_DIR, lambda_dir)),
            timeout=Duration.seconds(timeout),
            memory_size=256,
            environment=environment,
        )
