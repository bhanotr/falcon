import os
import aws_cdk as cdk
from falcon_stack.falcon_stack import FalconStack

app = cdk.App()

openai_key = app.node.try_get_context("openai_key")
if not openai_key:
    # Allow synth/bootstrap to proceed with a dummy key
    openai_key = "dummy-key"

FalconStack(
    app,
    "FalconStack",
    openai_key=openai_key,
    env=cdk.Environment(
        account=os.getenv("CDK_DEFAULT_ACCOUNT", "777459856565"),
        region=os.getenv("CDK_DEFAULT_REGION", "us-east-2"),
    ),
)

app.synth()
