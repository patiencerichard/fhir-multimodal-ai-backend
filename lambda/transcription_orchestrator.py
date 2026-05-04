# Transcription Orchestrator — Transcribe STANDARD + medical term mapping
# Generated from prompt.md Layer 2, Path A

import json
import os
import uuid
import boto3

transcribe = boto3.client("transcribe")
dynamodb = boto3.resource("dynamodb")
bedrock = boto3.client("bedrock-runtime")

SESSION_TABLE = os.environ["SESSION_TABLE"]
VOCAB_BUCKET = os.environ["VOCAB_BUCKET"]
SUPPORTED_LANGUAGES = json.loads(os.environ.get("SUPPORTED_LANGUAGES", '["sw-TZ"]'))

table = dynamodb.Table(SESSION_TABLE)


def handler(event, context):
    """Orchestrate transcription with language detection and medical term normalization."""
    for record in event["Records"]:
        body = json.loads(record["body"])
        bucket = body["bucket"]
        key = body["key"]
        job_id = f"transcribe-{uuid.uuid4().hex[:12]}"

        # Start transcription with language identification
        params = {
            "TranscriptionJobName": job_id,
            "Media": {"MediaFileUri": f"s3://{bucket}/{key}"},
            "OutputBucketName": bucket,
            "OutputKey": f"transcripts/{job_id}.json",
        }

        # Use language identification if multiple languages configured
        if len(SUPPORTED_LANGUAGES) > 1:
            params["IdentifyLanguage"] = True
            params["LanguageOptions"] = SUPPORTED_LANGUAGES
        else:
            params["LanguageCode"] = SUPPORTED_LANGUAGES[0]

        transcribe.start_transcription_job(**params)

        # Store session for downstream processing
        table.put_item(Item={
            "session_id": job_id,
            "source_key": key,
            "status": "TRANSCRIBING",
            "ttl": int(context.get_remaining_time_in_millis() / 1000) + 7200,
        })

    return {"statusCode": 200}


def normalize_medical_terms(transcript, language_code):
    """Map local-language symptoms to SNOMED CT concepts via Bedrock Haiku."""
    prompt = f"""Extract medical symptoms from this {language_code} transcript 
and map each to a SNOMED CT concept. Return JSON array only.
Transcript: {transcript}
Format: [{{"original": "...", "english": "...", "snomed_code": "..."}}]"""

    response = bedrock.invoke_model(
        modelId="anthropic.claude-3-haiku-20240307-v1:0",
        body=json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 1024,
            "messages": [{"role": "user", "content": prompt}],
        }),
    )
    return json.loads(json.loads(response["body"].read())["content"][0]["text"])
