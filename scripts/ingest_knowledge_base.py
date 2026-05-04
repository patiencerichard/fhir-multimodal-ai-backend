"""Bedrock Knowledge Base ingestion — upload PDFs and trigger sync."""
import boto3
import os
import sys

s3 = boto3.client("s3")
bedrock_agent = boto3.client("bedrock-agent")

BUCKET = os.environ.get("KB_BUCKET", "clinical-ai-knowledge")
KB_ID = os.environ.get("KNOWLEDGE_BASE_ID")
DS_ID = os.environ.get("DATA_SOURCE_ID")
DOCS_DIR = os.environ.get("DOCS_DIR", "./guidelines")


def upload_documents():
    for fname in os.listdir(DOCS_DIR):
        if fname.lower().endswith(".pdf"):
            key = f"guidelines/{fname}"
            s3.upload_file(os.path.join(DOCS_DIR, fname), BUCKET, key)
            print(f"Uploaded: {key}")


def start_ingestion():
    response = bedrock_agent.start_ingestion_job(
        knowledgeBaseId=KB_ID, dataSourceId=DS_ID
    )
    job_id = response["ingestionJob"]["ingestionJobId"]
    print(f"Ingestion started: {job_id}")


if __name__ == "__main__":
    upload_documents()
    if KB_ID and DS_ID:
        start_ingestion()
    else:
        print("Set KNOWLEDGE_BASE_ID and DATA_SOURCE_ID to trigger ingestion.")
