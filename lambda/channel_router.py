# Channel Router — detect input type and route to correct pipeline
# Generated from prompt.md Layer 2

import json
import boto3

sqs = boto3.client("sqs")
s3 = boto3.client("s3")

AUDIO_EXTENSIONS = {".mp4", ".m4a", ".wav", ".ogg"}
VIDEO_EXTENSIONS = {".mp4", ".mov"}
COUGH_PREFIX = "cough/"

def handler(event, context):
    """Route incoming uploads to the correct processing pipeline."""
    for record in event["Records"]:
        bucket = record["s3"]["bucket"]["name"]
        key = record["s3"]["object"]["key"]
        size = record["s3"]["object"]["size"]

        channel = detect_channel(key, size)

        if channel == "voice":
            if not validate_audio(size):
                return error_response("Audio exceeds 3 minute limit")
            route_to_queue(bucket, key, "voice-intake-queue")

        elif channel == "video":
            if not validate_video(size):
                return error_response("Video exceeds 50MB limit")
            route_to_queue(bucket, key, "rppg-intake-queue")

        elif channel == "cough":
            route_to_queue(bucket, key, "cough-intake-queue")

        else:
            route_to_queue(bucket, key, "text-intake-queue")

    return {"statusCode": 200, "body": json.dumps({"routed": len(event["Records"])})}


def detect_channel(key, size):
    if key.startswith(COUGH_PREFIX):
        return "cough"
    ext = "." + key.rsplit(".", 1)[-1].lower() if "." in key else ""
    if ext in VIDEO_EXTENSIONS and size > 5_000_000:
        return "video"
    if ext in AUDIO_EXTENSIONS:
        return "voice"
    return "text"


def validate_audio(size):
    # ~180s at 128kbps = ~2.7MB. Reject > 10MB as safety margin
    return size <= 10_000_000


def validate_video(size):
    return size <= 50_000_000


def route_to_queue(bucket, key, queue_name):
    queue_url = sqs.get_queue_url(QueueName=queue_name)["QueueUrl"]
    sqs.send_message(
        QueueUrl=queue_url,
        MessageBody=json.dumps({"bucket": bucket, "key": key}),
        MessageGroupId=key.split("/")[0],
        MessageDeduplicationId=key,
    )


def error_response(msg):
    return {"statusCode": 400, "body": json.dumps({"error": msg})}
