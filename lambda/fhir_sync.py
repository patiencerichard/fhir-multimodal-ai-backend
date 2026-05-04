# FHIR Sync — DynamoDB Streams → HealthLake FHIR write
# Generated from prompt.md Layer 4

import json
import os
import boto3

healthlake = boto3.client("healthlake")

DATASTORE_ID = os.environ["HEALTHLAKE_DATASTORE_ID"]


def handler(event, context):
    """Transform offline encounters from DynamoDB Streams into HealthLake FHIR resources."""
    written = 0

    for record in event["Records"]:
        if record["eventName"] not in ("INSERT", "MODIFY"):
            continue

        item = record["dynamodb"]["NewImage"]
        sync_status = item.get("sync_status", {}).get("S", "")

        if sync_status != "PENDING":
            continue

        resource_type = item.get("resource_type", {}).get("S", "Encounter")
        resource_body = json.loads(item.get("fhir_resource", {}).get("S", "{}"))

        # Tag as offline-origin
        resource_body.setdefault("meta", {})
        resource_body["meta"]["tag"] = [
            {"system": "sync-origin", "code": "offline-origin"}
        ]

        healthlake.create_resource(
            DatastoreId=DATASTORE_ID,
            ResourceType=resource_type,
            ResourceBody=json.dumps(resource_body),
        )
        written += 1

    return {"statusCode": 200, "resources_synced": written}
