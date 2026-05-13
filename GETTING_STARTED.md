# Getting Started — Deploy in 5 Days

## Day 1: Infrastructure (Terraform)

```bash
# Clone the repo
git clone https://github.com/patiencerichard/fhir-multimodal-ai-backend.git
cd fhir-multimodal-ai-backend

# Configure your deployment
cp terraform/terraform.tfvars.example terraform/terraform.tfvars
```

Edit `terraform/terraform.tfvars`:
```hcl
project_name         = "chw-triage"
primary_region       = "us-east-1"
supported_languages  = ["sw-TZ", "sw-KE", "so-SO", "en-ZA"]
monthly_budget_limit = 300
fhir_retention_years = 7
waf_geo_restriction  = ["TZ", "US"]
cognito_callback_urls = ["https://your-app.com/callback"]
```

Deploy:
```bash
cd terraform
terraform init
terraform plan    # Review what will be created
terraform apply   # Type 'yes' to deploy (~15 min)
```

This creates: VPC, HealthLake, Aurora pgvector, ECS cluster, 7 Lambdas, Cognito, WAF, CloudWatch dashboard, Budgets, S3 buckets, SQS queues, AppSync.

## Day 2: Clinical Knowledge Base

Upload your country's treatment guidelines:
```bash
# Upload PDFs to the knowledge base S3 bucket
aws s3 cp your-moh-guidelines.pdf s3://chw-triage-clinical-knowledge/
aws s3 cp who-imci-guidelines.pdf s3://chw-triage-clinical-knowledge/

# Trigger KB sync
cd scripts
python ingest_knowledge_base.py
```

## Day 3: Deploy Lambda Code + rPPG Container

```bash
# Lambda code is auto-deployed by Terraform, but to update:
cd lambda
zip channel_router.zip channel_router.py
aws lambda update-function-code \
  --function-name chw-triage-channel-router \
  --zip-file fileb://channel_router.zip

# Build and push rPPG container
cd ../container
./build-and-push.sh
```

## Day 4: Configure Transcribe Vocabularies

Create a custom vocabulary file per language (tab-separated):
```
# vocab/sw-TZ-medical-vocab.txt
Phrase	SoundsLike	IPA	DisplayAs
homa			fever
kikohozi			cough
kifua kikuu			tuberculosis
kuharisha			diarrhea
dharura			emergency
mjamzito			pregnant
```

Upload:
```bash
aws s3 cp vocab/sw-TZ-medical-vocab.txt s3://chw-triage-audio/vocab/
aws transcribe create-vocabulary \
  --vocabulary-name sw-TZ-medical \
  --language-code sw-TZ \
  --vocabulary-file-uri s3://chw-triage-audio/vocab/sw-TZ-medical-vocab.txt
```

## Day 5: Test

```bash
# Run unit tests
cd tests
pip install pytest
pytest test_lambdas.py -v

# Run load test (requires locust)
pip install locust
locust -f load_test.py --host https://your-appsync-url
```

## How It Works (End-to-End Flow)

1. CHW opens Flutter app → records voice symptoms in Swahili
2. Audio uploaded to S3 via presigned URL
3. `channel_router` Lambda detects audio → routes to voice pipeline
4. `transcription_orchestrator` calls Transcribe Standard (sw-TZ) → gets transcript
5. Bedrock Haiku maps Swahili symptoms to SNOMED CT codes
6. `clinical_reasoning` Lambda invokes Bedrock Sonnet with RAG context
7. Returns triage (EMERGENCY/URGENT/ROUTINE/SELF_CARE) in English + Swahili
8. FHIR Encounter + Observations written to HealthLake
9. Result displayed to CHW with recommended actions

## Outputs After Deployment

| Resource | Where to find it |
|----------|-----------------|
| FHIR API | HealthLake console → your datastore |
| GraphQL API | AppSync console → chw-triage-api |
| Dashboard | CloudWatch → Dashboards → chw-triage-dashboard |
| Logs | CloudWatch → Log groups → /aws/lambda/chw-triage-* |
| Budget alerts | AWS Budgets → chw-triage-monthly |

## Troubleshooting

See the TROUBLESHOOTING section in `prompt.md` for 8 common issues and fixes.
