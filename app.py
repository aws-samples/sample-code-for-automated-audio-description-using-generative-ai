#!/usr/bin/env python3
"""CDK App entry point for the DVI Narration sample."""
import aws_cdk as cdk

from infrastructure.pipeline_stack import PipelineStack
from infrastructure.dashboard_stack import DashboardStack

app = cdk.App()

env = cdk.Environment(
    account=app.node.try_get_context("account") or None,
    region=app.node.try_get_context("region") or "us-east-1",
)

# Pipeline stack: S3, DynamoDB, Lambdas, Step Functions
pipeline = PipelineStack(app, "DviPipelineStack", env=env)

# Dashboard stack: Cognito, API Gateway, CloudFront, Frontend
DashboardStack(
    app,
    "DviDashboardStack",
    pipeline_bucket_name=pipeline.bucket.bucket_name,
    pipeline_table_name=pipeline.table.table_name,
    state_machine_arn=pipeline.state_machine.state_machine_arn,
    env=env,
)

app.synth()
