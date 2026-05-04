# FHIR-First: Multimodal Clinical AI for Community Health Workers

> Production-ready, FHIR R4-compliant multimodal clinical AI backend on AWS for low-resource health environments with unreliable connectivity and multilingual patient populations.

## What This Does

One prompt generates complete infrastructure for a clinical AI system that:

- **Voice** — Accepts patient symptoms in 100+ languages via Amazon Transcribe
- **Camera** — Estimates heart rate and SpO2 from a phone camera (rPPG with skin-tone bias mitigation)
- **Cough** — Screens cough audio for TB risk using Bedrock Claude + MFCC analysis
- **Triage** — Synthesizes all inputs into structured clinical decisions via Bedrock RAG
- **Offline** — Works fully offline with rule-based IMCI triage, syncs on reconnect
- **FHIR R4** — All data stored as standards-compliant resources in AWS HealthLake

**Cost: ~$0.014 per encounter | $215/month for 15,000 encounters**

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                  CHW MOBILE APP (Flutter)                    │
│  ┌────────┐  ┌────────┐  ┌────────┐  ┌─────────────────┐   │
│  │ Voice  │  │ Camera │  │ Cough  │  │ Offline IMCI    │   │
│  │ Record │  │ rPPG   │  │ Samples│  │ Triage Engine   │   │
│  └───┬────┘  └───┬────┘  └───┬────┘  └─────────────────┘   │
│      └───────────┼───────────┘                              │
│                  ▼                                           │
│          S3 Presigned Upload (queue if offline)              │
└──────────────────┬──────────────────────────────────────────┘
                   │
       ┌───────────▼───────────┐
       │  API Gateway + WAF    │
       │  Cognito Authorizer   │
       └───────────┬───────────┘
                   │
    ┌──────────────┼──────────────┐
    ▼              ▼              ▼
┌────────┐  ┌───────────┐  ┌───────────┐
│ Voice  │  │ rPPG      │  │ Cough     │
│Pipeline│  │ Pipeline  │  │ Pipeline  │
│SQS→λ→ │  │ S3→ECS    │  │ StepFns→  │
│Transcr.│  │ Fargate   │  │ λ→Bedrock │
└───┬────┘  └─────┬─────┘  └─────┬─────┘
    └──────────────┼──────────────┘
                   ▼
       ┌───────────────────────┐
       │  Clinical Reasoning   │
       │  Engine (Bedrock)     │
       │  RAG: Aurora pgvector │
       └───────────┬───────────┘
                   ▼
       ┌───────────────────────┐
       │   AWS HealthLake      │
       │   (FHIR R4 Store)     │
       └───────────────────────┘
```

## Repository Structure

```
├── terraform/          # Complete IaC (HealthLake, Bedrock, ECS, Lambda, VPC, etc.)
├── lambda/             # 7 Python 3.11 Lambda functions
├── container/          # Dockerfile + rPPG processor (CHROM algorithm)
├── scripts/            # KB ingestion, deployment helpers
├── fhir-samples/       # Sample FHIR R4 resources (Patient, Encounter, Observation)
├── docs/               # CHW user guide, architecture docs
├── tests/              # Locust load tests
└── prompt.md           # The complete prompt (competition submission)
```

## AWS Services Used (18)

| Category | Services |
|----------|----------|
| Compute | Lambda, ECS Fargate |
| AI/ML | Bedrock (Claude Sonnet/Haiku, Titan Embeddings), Transcribe, Rekognition |
| Storage | S3, DynamoDB, Aurora Serverless v2 (pgvector) |
| Healthcare | HealthLake (FHIR R4) |
| Integration | Step Functions, SQS FIFO, AppSync (GraphQL) |
| Security | Cognito, KMS, WAF |
| Networking | VPC, VPC Endpoints, CloudFront |
| Monitoring | CloudWatch, CloudTrail, Budgets, SNS |

## Prerequisites

- AWS Account with Organizations enabled
- Terraform >= 1.5
- Docker (for rPPG container build)
- Python 3.11+
- Bedrock Claude model access granted
- HealthLake-available region (us-east-1, us-east-2, us-west-2, ap-south-1, eu-west-1, eu-west-2, ap-southeast-2)

## Quick Start

```bash
# 1. Clone
git clone https://github.com/tibabu-health/fhir-multimodal-ai-backend.git
cd fhir-multimodal-ai-backend

# 2. Configure
cp terraform/terraform.tfvars.example terraform/terraform.tfvars
# Edit: region, language codes, project name, budget limit

# 3. Deploy
cd terraform && terraform init && terraform apply

# 4. Build & push rPPG container
cd ../container && ./build-and-push.sh

# 5. Ingest clinical guidelines
cd ../scripts && python ingest_knowledge_base.py

# 6. Run load tests
cd ../tests && locust -f load_test.py
```

## Well-Architected Alignment

- **Security** — KMS CMK encryption, Cognito RBAC, WAF, VPC private subnets, no public endpoints
- **Reliability** — Cross-region failover, 3-tier offline, SQS FIFO dedup, Step Functions retry
- **Performance** — Model routing by complexity, <3s EMERGENCY detection, parallel cough processing
- **Cost** — Scale-to-zero Fargate/Aurora, progressive budget degradation, $0.014/encounter
- **Sustainability** — Serverless-first, reject oversized inputs early, efficient RAG chunking

## Key Design Decisions

1. **Transcribe Standard, NOT Medical** — Medical is en-US only. Standard supports 100+ languages at lower cost ($0.024 vs $0.075/min)
2. **HealthLake region awareness** — Not available in af-south-1. Data residency via KMS CMK + contractual controls
3. **rPPG skin-tone bias mitigation** — Fitzpatrick V-VI adaptive preprocessing + mandatory confidence scoring + never used alone for clinical decisions
4. **Progressive budget degradation** — Disables expensive paths first, NEVER disables voice triage (cheapest + most critical)
5. **Country-agnostic** — All country-specific values (ID URIs, languages, guidelines, drugs) injected via configuration

## License

MIT

## Competition

Submitted to [AWS Prompt the Planet Challenge](https://awsprompttheplanet.devpost.com/) — March–June 2026.
