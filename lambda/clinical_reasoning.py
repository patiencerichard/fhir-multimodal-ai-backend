# Clinical Reasoning — Bedrock invoke + RAG + FHIR write
# Generated from prompt.md Layer 3

import json
import os
import uuid
from datetime import datetime

import boto3

bedrock = boto3.client("bedrock-runtime")
bedrock_agent = boto3.client("bedrock-agent-runtime")
healthlake = boto3.client("healthlake")

DATASTORE_ID = os.environ["HEALTHLAKE_DATASTORE_ID"]
KB_ID = os.environ["KNOWLEDGE_BASE_ID"]
MODEL_ID = os.environ.get("MODEL_ID", "anthropic.claude-sonnet-4-20250514-v1:0")
HAIKU_MODEL_ID = "anthropic.claude-3-haiku-20240307-v1:0"
MAX_TOKENS_FOR_SONNET = 2000


def handler(event, context):
    """Synthesize patient data into structured triage via Bedrock RAG."""
    encounter = event["encounter"]

    # Retrieve relevant clinical guidelines
    rag_context = retrieve_guidelines(encounter)

    # Choose model based on token estimate
    model_id = MODEL_ID
    if estimate_tokens(encounter) > MAX_TOKENS_FOR_SONNET:
        model_id = HAIKU_MODEL_ID

    # Build clinical reasoning prompt
    prompt = build_prompt(encounter, rag_context)

    # Invoke Bedrock
    response = bedrock.invoke_model(
        modelId=model_id,
        body=json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 2048,
            "messages": [{"role": "user", "content": prompt}],
        }),
    )
    result = json.loads(json.loads(response["body"].read())["content"][0]["text"])

    # Write FHIR Encounter + DiagnosticReport
    write_fhir_encounter(encounter, result)

    return {"statusCode": 200, "triage": result}


def retrieve_guidelines(encounter):
    """RAG retrieval from Bedrock Knowledge Base."""
    query = f"{encounter.get('transcript_english', '')} {encounter.get('region', '')}"
    response = bedrock_agent.retrieve(
        knowledgeBaseId=KB_ID,
        retrievalQuery={"text": query[:1000]},
        retrievalConfiguration={"vectorSearchConfiguration": {"numberOfResults": 5}},
    )
    return "\n".join(r["content"]["text"] for r in response["retrievalResults"])


def build_prompt(encounter, rag_context):
    return f"""You are a clinical decision support AI for community health workers.
You ASSIST — you do NOT replace — licensed clinicians.

PATIENT DATA:
- Symptoms ({encounter.get('source_language', 'en')}): {encounter.get('transcript_original', '')}
- Symptoms (English): {encounter.get('transcript_english', '')}
- rPPG vitals (PRELIMINARY): HR {encounter.get('heart_rate', 'N/A')} bpm (confidence: {encounter.get('hr_confidence', 'N/A')}), SpO2 {encounter.get('spo2', 'N/A')}% (confidence: {encounter.get('spo2_confidence', 'N/A')})
- Cough screening: {encounter.get('cough_risk_score', 'N/A')}/100 ({encounter.get('risk_tier', 'N/A')})
- Age: {encounter.get('age', 'N/A')}, Sex: {encounter.get('sex', 'N/A')}, Pregnancy: {encounter.get('pregnancy', 'N/A')}
- Conditions: {encounter.get('conditions', 'None')}
- Medications: {encounter.get('medications', 'None')}
- Allergies: {encounter.get('allergies', 'None')}
- Location: {encounter.get('district', '')}, {encounter.get('region', '')}
- Guidelines: {rag_context}

INSTRUCTIONS:
1. Top 3 differential diagnoses with reasoning
2. Triage: EMERGENCY / URGENT / ROUTINE / SELF_CARE
3. Immediate CHW actions
4. What requires a physician
5. If TB risk > 60 OR SpO2 < 94%: ALWAYS facility referral
6. If chest pain + dyspnea + age > 35: ALWAYS EMERGENCY
7. Respond in English AND {encounter.get('source_language', 'en')}
8. Flag drug interactions

SAFETY: Never diagnose. Never prescribe. If uncertain: escalate.

Return JSON: {{"triage_category":"...","differentials":[...],"chw_actions":[...],"physician_referral_reasons":[...],"drug_interactions":[...],"response_english":"...","response_local_language":"...","confidence":"..."}}"""


def write_fhir_encounter(encounter, result):
    resource = {
        "resourceType": "Encounter",
        "id": str(uuid.uuid4()),
        "status": "finished",
        "class": {"code": "AMB", "display": "ambulatory"},
        "subject": {"reference": f"Patient/{encounter['patient_id']}"},
        "period": {"start": datetime.utcnow().isoformat() + "Z"},
        "reasonCode": [{"text": encounter.get("transcript_english", "")}],
    }
    healthlake.create_resource(
        DatastoreId=DATASTORE_ID,
        ResourceType="Encounter",
        ResourceBody=json.dumps(resource),
    )


def estimate_tokens(encounter):
    text = json.dumps(encounter)
    return len(text) // 4
