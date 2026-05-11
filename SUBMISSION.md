# AWS Prompt the Planet — Submission

## Title
FHIR Multimodal Clinical AI Backend for Community Health Workers

---

## Summary (one paragraph)
A production-ready AWS backend that gives Community Health Workers
in low-resource settings an AI-powered clinical triage tool that
works in 100+ languages, runs offline, and costs ~$0.014 per
encounter. It combines voice transcription (Amazon Transcribe
Standard), camera-based vitals estimation via rPPG (ECS Fargate),
TB cough screening (Bedrock + MFCC audio features), and FHIR R4
data storage (HealthLake) — all with a three-tier offline fallback
so CHWs in areas with no connectivity can still triage patients
using embedded IMCI rules, syncing to the cloud when connectivity
returns.

---

## Prerequisites
1. AWS Account with Organizations enabled
2. AWS CLI v2 with AdministratorAccess (or scoped deployment role)
3. Terraform >= 1.5
4. Docker (for rPPG container build)
5. Python 3.11+ (for Lambda packaging)
6. HealthLake-available region: us-east-1, us-east-2, us-west-2,
   ap-south-1, eu-west-1, eu-west-2, ap-southeast-2
   ⚠️ NOT available in af-south-1 or me-south-1
7. Bedrock Claude model access granted in your region
8. Amazon Transcribe Standard enabled (NOT Medical — Medical is
   en-US only; Standard supports 100+ languages)
9. Country MoH treatment guidelines (PDF) for RAG ingestion
10. Custom Transcribe vocabulary file per target language

---

## Use Case

**Who this is for:**
- Health-tech startups deploying AI triage in emerging markets
- NGOs digitizing community health worker programs
- Government health ministries building national digital health
- Developers building offline-first clinical apps

**Problem it solves:**
CHWs in low-resource settings lack tools that work with low-literacy
populations (voice-first), local languages, unreliable connectivity,
and basic Android smartphones — without specialized medical devices.

**Expected outcome:**
After running this prompt you will have:
- Complete Terraform IaC for the entire backend
- 7 Lambda functions (Python 3.11) for the processing pipeline
- ECS Fargate container for camera-based vitals (rPPG)
- Bedrock RAG knowledge base with clinical guidelines
- Sample FHIR R4 resources (Patient, Encounter, Observation,
  DiagnosticReport)
- CloudWatch dashboard (8 panels, import-ready)
- Bilingual CHW user guide
- Locust load test script (50 concurrent CHW sessions)
- Estimated cost: ~$215/month for 15,000 encounters (~$0.014 each)

---

## The Prompt

> See `prompt.md` — submit verbatim as the "Details" section.

**Segment breakdown:**

| Section | What it builds |
|---------|---------------|
| **Layer 1 — FHIR Foundation** | HealthLake R4 datastore, KMS CMK, LOINC-coded Observations, SMART on FHIR auth, CloudTrail audit |
| **Layer 2A — Voice Intake** | Transcribe Standard (100+ languages), custom vocabulary per language, SNOMED CT mapping via Bedrock Haiku |
| **Layer 2B — Camera Vitals (rPPG)** | ECS Fargate CHROM algorithm, skin-tone adaptive preprocessing (Fitzpatrick I-VI), confidence scoring, FHIR Observation write |
| **Layer 2C — Cough TB Screening** | 5-sample MFCC extraction, Step Functions parallel workflow, Bedrock Haiku classification, risk score 0-100 |
| **Layer 3 — Clinical Reasoning** | Bedrock Claude Sonnet RAG triage, multilingual output, safety guardrails, FHIR Encounter write |
| **Layer 4 — Offline Sync** | Three connectivity tiers, DynamoDB Streams → HealthLake, AppSync conflict resolution, embedded IMCI fallback |
| **Layer 5 — Monitoring & Cost** | 8-panel CloudWatch dashboard, AWS Budgets progressive degradation (rPPG → cough → Haiku), WAF, VPC private subnets |

---

## AWS Services Used
Amazon HealthLake · Amazon Bedrock (Claude Sonnet, Haiku, Titan
Embeddings) · Amazon Transcribe · Amazon Rekognition · AWS Lambda ·
Amazon ECS Fargate · Amazon S3 · Amazon DynamoDB · Amazon Aurora
Serverless v2 (pgvector) · AWS Step Functions · Amazon SQS FIFO ·
AWS AppSync · Amazon Cognito · AWS KMS · AWS WAF · Amazon VPC ·
Amazon CloudWatch · AWS CloudTrail · AWS Budgets · Amazon SNS

---

## AWS Well-Architected Alignment

| Pillar | Key implementation |
|--------|--------------------|
| Operational Excellence | CloudWatch 8-panel dashboard, Step Functions observability, progressive degradation not hard failure |
| Security | KMS CMK, SMART on FHIR + Cognito RBAC, WAF rate-limit + geo, VPC private subnets, PII masking via Bedrock Guardrails |
| Reliability | Three-tier offline architecture, cross-region Bedrock fallback, SQS FIFO exactly-once, ECS auto-scaling |
| Performance Efficiency | Model routing by complexity (Haiku fast / Sonnet deep), EMERGENCY path < 3s, S3 multipart 256KB chunks |
| Cost Optimization | Scale-to-zero Fargate, Aurora Serverless v2 0.5 ACU idle, Transcribe Standard vs Medical saves 68%, budget-triggered degradation |
| Sustainability | Serverless-first, scale-to-zero all compute, reject oversized inputs early |

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| HealthLake creation fails | Wrong region — use us-east-1, us-east-2, us-west-2, ap-south-1, eu-west-1, eu-west-2, ap-southeast-2 |
| Transcribe returns garbage for non-English | You used Transcribe Medical (en-US only) — switch to Transcribe Standard |
| Bedrock "model not available" | Grant Claude model access in Bedrock console → Model access |
| rPPG low confidence for most patients | Expected for Fitzpatrick V-VI — verify skin-tone adaptive preprocessing is on; increase clip to 30s |
| Offline encounters not syncing | Check DynamoDB Streams enabled; check fhir_sync Lambda logs for HealthLake write errors |
| Triage latency > 45s | Check CloudWatch panel 4 — common causes: Fargate cold start (raise min tasks to 1), Aurora cold start (raise min ACU to 1) |
| Budget exceeded despite controls | Budget actions have ~15 min delay — set threshold at 80% to trigger early |
