# rPPG Result Handler — apply confidence scoring, write FHIR Observation
# Generated from prompt.md Layer 2, Path B

import json
import os
import uuid
from datetime import datetime

import boto3

healthlake = boto3.client("healthlake")

DATASTORE_ID = os.environ["HEALTHLAKE_DATASTORE_ID"]


def handler(event, context):
    """Receive Fargate rPPG results, apply confidence + skin-tone flag, write FHIR."""
    result = event["detail"]

    hr_obs = build_observation(
        patient_id=result["patient_id"],
        encounter_id=result["encounter_id"],
        loinc_code="8867-4",
        display="Heart rate",
        value=result["heart_rate"],
        unit="beats/minute",
        confidence=result["hr_confidence"],
        skin_tone_flag=result["skin_tone_flag"],
    )

    spo2_obs = build_observation(
        patient_id=result["patient_id"],
        encounter_id=result["encounter_id"],
        loinc_code="59408-5",
        display="Oxygen saturation",
        value=result["spo2"],
        unit="%",
        confidence=result["spo2_confidence"],
        skin_tone_flag=result["skin_tone_flag"],
    )

    for obs in [hr_obs, spo2_obs]:
        healthlake.create_resource(
            DatastoreId=DATASTORE_ID,
            ResourceType="Observation",
            ResourceBody=json.dumps(obs),
        )

    return {"statusCode": 200, "observations_written": 2}


def build_observation(patient_id, encounter_id, loinc_code, display, value, unit, confidence, skin_tone_flag):
    return {
        "resourceType": "Observation",
        "id": str(uuid.uuid4()),
        "status": "preliminary",
        "code": {
            "coding": [{"system": "http://loinc.org", "code": loinc_code, "display": display}]
        },
        "subject": {"reference": f"Patient/{patient_id}"},
        "encounter": {"reference": f"Encounter/{encounter_id}"},
        "effectiveDateTime": datetime.utcnow().isoformat() + "Z",
        "valueQuantity": {"value": value, "unit": unit},
        "note": [{
            "text": "Estimated via rPPG camera analysis. NOT a medical device measurement. "
                    "Requires clinical confirmation with pulse oximeter before treatment decisions."
        }],
        "extension": [
            {"url": "measurement-confidence", "valueString": confidence},
            {"url": "skin-tone-flag", "valueString": skin_tone_flag},
        ],
    }
