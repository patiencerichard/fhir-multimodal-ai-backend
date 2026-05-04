# Budget Enforcer — progressive service degradation
# Generated from prompt.md Layer 5

import json
import os
import boto3

ecs = boto3.client("ecs")
lambda_client = boto3.client("lambda")
sns = boto3.client("sns")

ECS_CLUSTER = os.environ["ECS_CLUSTER"]
RPPG_SERVICE = os.environ["RPPG_SERVICE"]
COUGH_LAMBDA = os.environ["COUGH_LAMBDA_NAME"]
ALERT_TOPIC = os.environ["ALERT_TOPIC_ARN"]


def handler(event, context):
    """Progressive degradation: rPPG → cough → route-to-Haiku. Never disable voice."""
    message = json.loads(event["Records"][0]["Sns"]["Message"])
    threshold = message.get("ThresholdBreached", "")

    if "80" in threshold:
        # 80% budget: disable rPPG (most expensive)
        ecs.update_service(
            cluster=ECS_CLUSTER, service=RPPG_SERVICE, desiredCount=0
        )
        notify("Budget 80%: rPPG pipeline disabled (scale-to-zero)")

    elif "90" in threshold:
        # 90% budget: also disable cough screening
        lambda_client.put_function_concurrency(
            FunctionName=COUGH_LAMBDA, ReservedConcurrentExecutions=0
        )
        notify("Budget 90%: Cough screening disabled")

    elif "100" in threshold:
        # 100% budget: route all to Haiku (cheapest model)
        # Voice triage NEVER disabled
        notify("Budget 100%: All routing switched to Haiku. Voice triage remains active.")

    return {"statusCode": 200}


def notify(msg):
    sns.publish(TopicArn=ALERT_TOPIC, Subject="Budget Enforcer Action", Message=msg)
