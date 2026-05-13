# FHIR Multimodal Clinical AI Backend for Community Health Workers

> Complete FHIR R4 clinical AI backend for Community Health Workers in low-resource settings — voice triage in 100+ languages, camera-based vitals estimation, TB cough screening, and offline-first sync. Cost: ~$0.014 per clinical encounter at 15,000/month.

Millions of Community Health Workers (CHWs) in Africa, South Asia, and Southeast Asia conduct clinical triage with no decision support tools — relying on memory, paper forms, and basic training. They work in areas with no reliable internet, serve patients who speak dozens of local languages, and use basic Android smartphones as their only technology.

This prompt generates a complete, production-ready AWS backend that gives CHWs an AI-powered triage assistant that:
- Understands voice in 100+ languages (Swahili, Somali, Kinyarwanda, Hindi, Indonesian, and more)
- Estimates heart rate and SpO2 from the phone camera — no pulse oximeter needed
- Screens for TB from cough audio recordings
- Works fully offline with embedded IMCI rules, syncing when connectivity returns
- Costs ~$0.014 per encounter — affordable at national scale

The architecture is country-agnostic and language-pluggable. All country-specific values (national ID URI, language codes, clinical guidelines, drug formularies) are injected via configuration — not hardcoded.

You are an AWS Solutions Architect and clinical systems engineer. Build a production-ready, FHIR R4-compliant multimodal clinical AI backend on AWS targeting low-resource health environments with unreliable connectivity and multilingual patient populations.

## PREREQUISITES

1. AWS Account with Organizations enabled
2. AWS CLI v2 configured with AdministratorAccess
3. Terraform >= 1.5 installed
4. Docker installed (for rPPG container build)
5. Python 3.11+ (for Lambda packaging)
6. AWS services enabled in your region:
   - Amazon HealthLake (regions: us-east-1, us-east-2, us-west-2, ap-south-1, eu-west-1, eu-west-2, ap-southeast-2, ca-central-1)
   - Amazon Bedrock with Claude model access granted
   - Amazon Transcribe Standard (NOT Medical — Medical is en-US only)
7. Clinical guideline PDFs for RAG ingestion (MoH guidelines, WHO IMCI)
8. Custom vocabulary files per target language

REGIONAL NOTES:
- HealthLake NOT available in af-south-1, me-south-1, or most Asia-Pacific.
- Transcribe Medical is en-US ONLY. Use Transcribe STANDARD (100+ languages): sw-TZ, so-SO, rw-RW, fr-FR, hi-IN, bn-IN, id-ID, es-US, pt-BR, and more.
- STREAMING LIMITATION: sw-TZ, rw-RW, bn-IN are batch-only. Use StartTranscriptionJob. Languages with streaming: so-SO, fr-FR, hi-IN, id-ID, es-US, pt-BR.
- Bedrock Claude varies by region. Use cross-region inference (Geo/Global) for availability.

## USE CASE

WHO: Health-tech startups, NGOs, government health ministries, developers building offline-first clinical apps.

PROBLEM: CHWs lack tools that work with low-literacy populations (voice-first), local languages, unreliable connectivity, basic smartphones, and tight budgets.

EXPECTED OUTCOME: Complete Terraform IaC, 7 Lambda functions, ECS Fargate rPPG container, Bedrock RAG knowledge base, FHIR R4 samples, CloudWatch dashboard, bilingual CHW guide, Locust load test. Cost: ~$215/month for 15,000 encounters.

DEPLOYMENT: 5 days — Day 1: terraform apply, Day 2: upload guidelines, Day 3: deploy Lambdas + container, Day 4: configure vocabularies, Day 5: integration test.

COST vs ALTERNATIVES: This prompt $0.014/encounter ($215/mo) vs OpenAI GPT-4+Whisper $0.08-0.12 ($1,200-1,800/mo) vs Google Cloud Healthcare $0.05-0.08 ($750-1,200/mo). 85% cheaper than GPT-4 alternatives.

## ARCHITECTURE

```
CHW Android App (Flutter, offline-first)
  │ Voice        │ Camera       │ Cough
  ▼              ▼              ▼
LAYER 2 — Multimodal Intake Pipeline
  Path A: Transcribe Standard (100+ languages)
  Path B: ECS Fargate rPPG (CHROM algorithm)
  Path C: Step Functions + MFCC + Bedrock Haiku
  ▼
LAYER 3 — Clinical Reasoning (Bedrock Claude + RAG)
  ▼
LAYER 1 — HealthLake FHIR R4 Datastore (KMS CMK, CloudTrail)
LAYER 4 — Offline Sync (AppSync + DynamoDB, 3 tiers)
LAYER 5 — Monitoring & Cost Controls (CloudWatch 8 panels, Budgets, WAF)
```

## LAYER 1 — FHIR R4 DATA FOUNDATION

Deploy AWS HealthLake as the FHIR R4-compliant datastore:

- Resources: Patient, Observation, Condition, Encounter, DiagnosticReport, MedicationRequest, Practitioner, Organization
- SMART on FHIR authorization (Cognito + Lambda authorizer)
- Patient identity: National ID + facility code composite key as FHIR Identifier with system URI "urn:{country_code}:moh:national-id" (configurable per country)
- All Observations tagged with LOINC codes (mandatory):
  - Respiratory rate: LOINC 9279-1
  - SpO2: LOINC 59408-5
  - Temperature: LOINC 8310-5
  - Heart rate: LOINC 8867-4
  - Cough classification: custom extension "{project}:cough-risk-score"
- HealthLake encryption: AWS KMS CMK, automatic rotation every 365 days
- Audit: all FHIR read/write → CloudTrail → S3 (7-year retention, configurable per country's data retention laws)
- Deploy in HealthLake-available region. Use second region for DR failover.
- For data residency: KMS CMK controlled by local health authority + contractual data processing agreements
- Terraform resource: aws_healthlake_fhir_datastore

## LAYER 2 — MULTIMODAL INTAKE PIPELINE

### PATH A: MULTILINGUAL VOICE

CRITICAL: Use Transcribe STANDARD ($0.024/min), NOT Medical ($0.075/min, en-US only).

Language sets: East Africa (sw-TZ, sw-KE, so-SO, rw-RW, lg-IN, fr-FR, en-ZA), South Asia (hi-IN, bn-IN, ta-IN, en-IN), Southeast Asia (id-ID, vi-VN, tl-PH, ms-MY, en-AU), Latin America (es-US, pt-BR, en-US), West Africa (ha-NG, wo-SN, fr-FR, en-ZA).

Flow: Mobile → S3 (presigned URL, 3min expiry) → SQS FIFO → Lambda transcription orchestrator (auto-detect language, custom vocabulary) → medical term normalizer (Bedrock Haiku → SNOMED CT mapping) → Clinical Reasoning Lambda.

Example Swahili vocabulary: homa=fever, kikohozi=cough, kifua kikuu=tuberculosis, kuharisha=diarrhea, dharura=emergency.

Cost control: reject audio > 180 seconds.

### PATH B: CAMERA-BASED VITALS (rPPG)

Flow: 15-second camera clip → S3 multipart (256KB chunks) → Lambda validator (reject <720p, >50MB, <10s) → Rekognition face detection → ECS Fargate rPPG processor → FHIR Observation.

Container: python:3.11-slim, opencv-python-headless, scipy, numpy. CHROM algorithm with SKIN-TONE ADAPTIVE PREPROCESSING. Fitzpatrick I-IV: standard pipeline. Fitzpatrick V-VI: enhanced preprocessing + reduced confidence ceiling (max "moderate"). Runtime: ~8s on 0.5 vCPU/1GB. Auto-scale: min 0, max 10 tasks (CPU 70%).

CRITICAL FHIR flags: Observation.status="preliminary", note="NOT a medical device measurement. Requires pulse oximeter confirmation." Extensions: measurement-confidence (low|moderate|high), skin-tone-flag (standard|reduced-confidence).

ETHICAL: rPPG degrades for darker skin tones. Mitigations: explicit confidence scoring, never use SpO2 alone for decisions, always recommend device confirmation, monitor by skin tone in CloudWatch.

### PATH C: COUGH TB SCREENING

Flow: 5 cough samples (.wav) → Step Functions parallel → Lambda MFCC extraction (13 coefficients via scipy) → Bedrock Haiku classification → risk score 0-100 → FHIR DiagnosticReport.

Bedrock prompt for cough classification (inject MFCC values):
"You are a clinical audio analysis assistant supporting respiratory disease screening. Given MFCC summary statistics extracted from patient cough recordings, assess the likelihood of TB-pattern cough versus common respiratory illness.

IMPORTANT: This is a SCREENING tool, not a diagnostic. Your output helps prioritize patients for confirmatory testing (e.g., GeneXpert, sputum smear, chest X-ray).

MFCC data: {mfcc_summary}.
Patient context: age {age}, sex {sex}, HIV status {hiv_status}, prior TB history {tb_history}, region {region}.
Return JSON only:
{
  'risk_score': 0-100,
  'risk_tier': 'low|medium|high',
  'recommended_action': string (in English AND patient language),
  'confidence': 'low|medium|high',
  'referral_required': boolean,
  'suggested_test': 'GeneXpert|sputum_smear|chest_xray|none',
  'reasoning': 'brief clinical reasoning'
}"

Error handling: <3/5 samples succeed → INSUFFICIENT_DATA. Retry: 2x exponential backoff (30s). Fallback: symptom-only triage.

## LAYER 3 — CLINICAL REASONING (Bedrock)

Model routing: Full triage → Claude Sonnet (claude-sonnet-4-20250514). Cough/quick checks → Haiku. EMERGENCY → Haiku (<3s). Complex cases → Sonnet extended. Fallback → Titan Text Lite (cross-region).

RAG: S3 "{project}-clinical-knowledge" → Titan Embeddings V2 → Aurora Serverless v2 pgvector (0.5-2 ACU). Chunking: 512 tokens, 20% overlap. Max 5 chunks/query.

Master prompt: "You are a clinical decision support AI for community health workers. You ASSIST — you do NOT replace — licensed clinicians. Your role is to synthesize patient data into a structured triage recommendation.

PATIENT DATA:
- Symptoms (original language: {source_language}): {transcript_original}
- Symptoms (English translation): {transcript_english}
- rPPG vitals (PRELIMINARY — camera-estimated, NOT device-measured): HR {heart_rate} bpm (confidence: {hr_confidence}), SpO2 {spo2}% (confidence: {spo2_confidence})
- Cough screening score: {cough_risk_score}/100 ({risk_tier})
- Age: {age}, Sex: {sex}, Pregnancy: {pregnancy}
- Known conditions: {conditions}
- Current medications: {medications}
- Allergies: {allergies}
- Facility: {district}, {region}
- Retrieved guidelines: {rag_context}

INSTRUCTIONS:
1. Identify top 3 differential diagnoses with reasoning
2. Assign triage: EMERGENCY / URGENT / ROUTINE / SELF-CARE
3. List immediate CHW actions NOW
4. State what requires a physician — never exceed CHW scope
5. If TB risk > 60 OR SpO2 < 94%: ALWAYS recommend facility referral
6. If chest pain + dyspnea + age > 35: ALWAYS mark EMERGENCY
7. Respond in BOTH English AND patient's source language
8. Flag drug interactions against medications AND allergies
9. Reference retrieved clinical guidelines
10. Include available free/subsidized government medications

CRITICAL SAFETY RULES:
- NEVER diagnose. Use: 'suggests', 'consistent with', 'warrants evaluation for'
- NEVER recommend prescription medications or dosages
- NEVER provide mental health crisis intervention — route to specialist
- NEVER recommend surgical procedures
- If uncertain: ESCALATE. Never guess.
- All rPPG vitals are PRELIMINARY — always recommend device confirmation
- Drug allergy cross-reactivity: penicillin allergy → flag ALL beta-lactams

Return JSON: {triage_category, differentials, chw_actions, physician_referral_reasons, drug_interactions, response_english, response_local_language, response_language_code, guidelines_cited, confidence}."

Guardrails: Block medical misinformation, enable grounding, mask PII, deny prescription dosing/surgery/mental health crisis topics.

Latency: Full triage <45s, voice-only <15s, EMERGENCY <3s.

## LAYER 4 — OFFLINE-FIRST SYNC

Three connectivity tiers:
- FULL — stable internet: all 3 intake paths active, real-time Bedrock reasoning
- DEGRADED — intermittent/slow: voice + text only (no video upload), queue for sync
- OFFLINE — no connectivity: rule-based IMCI triage from embedded JSON, local storage only

Mobile app (Flutter):
- SQLite local cache: stores up to 200 patient encounters
- Hive encrypted storage: clinical data at rest (AES-256)
- Offline triage: rule-based fallback (IMCI decision tree, embedded as JSON in app bundle)
- Queue: all data tagged with sync_status: PENDING
- Offline triage clearly marked in UI: "This recommendation was generated OFFLINE using basic rules. Seek cloud-assisted triage when connectivity is restored."

AWS sync infrastructure:
- AppSync (GraphQL) with DynamoDB conflict resolution
- DynamoDB Streams → Lambda → HealthLake FHIR write (meta.tag = "offline-origin")
- Sync trigger: on connectivity restored OR manual CHW action
- Conflict resolution:
  - Vitals/observations: last-writer-wins (most recent is most relevant)
  - Clinical notes/assessments: manual review queue (DynamoDB GSI: conflict_flag = true)
  - Patient demographics: server-wins (prevent offline edits overwriting verified data)
- CloudFront + S3: cache clinical guidelines locally (updated weekly)

## LAYER 5 — MONITORING, COST CONTROLS & COMPLIANCE

CloudWatch Dashboard — 8 panels:
1. Triage volume by channel (voice/rPPG/cough) — 1hr rolling
2. Triage volume by language — 1hr rolling
3. Bedrock token consumption + estimated cost — daily
4. Average triage latency P50/P95 — 5min resolution
5. Offline encounter queue depth (DynamoDB item count)
6. FHIR write errors (HealthLake 4xx/5xx) — alarm if >1%
7. rPPG Fargate task duration — alarm if >60s avg
8. rPPG confidence distribution by skin tone — daily (equity monitoring)

Cost controls:
- AWS Budgets: configurable hard limit (default $300/month)
- Budget action → SNS → Lambda → progressive degradation:
  1. First: disable rPPG path (most expensive)
  2. Then: disable cough screening
  3. Last resort: route all to Haiku (NEVER disable voice triage — cheapest and most critical)
- Bedrock per-invoke cost check: if estimated tokens > 2000, route to Haiku not Sonnet
- Transcribe: reject audio > 3 minutes
- Reserved concurrency on clinical Lambda: max 50 (prevent runaway costs)

Monthly cost at 15,000 encounters: Bedrock ~$85, Transcribe ~$40, HealthLake ~$35, Fargate ~$25, Aurora ~$30. Total: ~$215/month ($0.014/encounter).

Compliance: KMS CMK rotation (365 days), VPC private subnets only, no public endpoints (API Gateway + WAF + Cognito), WAF rate-limit 100/IP/min + geo-restrict, CloudTrail all events encrypted (7-year retention), data residency via KMS CMK held by local health authority.

## REQUIRED OUTPUTS

Generate ALL of the following:

1. Terraform (HCL) — complete infrastructure:
   - HealthLake FHIR datastore + KMS CMK
   - Cognito User Pool (roles: CHW_BASIC, NURSE, PHYSICIAN, ADMIN)
   - S3 buckets (audio, video, knowledge base, audit logs — separate lifecycle policies)
   - SQS FIFO queues (audio intake, cough samples, sync queue)
   - Step Functions state machine (cough screening workflow)
   - ECS cluster + Fargate task definition (rPPG, scale-to-zero)
   - Aurora Serverless v2 + pgvector (0.5-2 ACU)
   - Bedrock Knowledge Base + S3 data source
   - AppSync GraphQL API + DynamoDB tables (sessions, sync queue, conflicts)
   - CloudWatch dashboard + alarms + Budget + SNS topics
   - WAF WebACL (rate limiting + geo-restriction)
   - VPC + private subnets + VPC endpoints (Bedrock, S3, DynamoDB, HealthLake)
   - IAM roles with least-privilege policies per Lambda

2. Lambda functions (Python 3.11):
   - channel_router.py — detect input type, validate, route to pipeline
   - transcription_orchestrator.py — Transcribe Standard + language detection + custom vocab + Haiku medical term mapping
   - rppg_result_handler.py — confidence scoring + skin-tone flag + FHIR Observation write
   - cough_feature_extractor.py — MFCC extraction (13 coefficients via scipy)
   - clinical_reasoning.py — Bedrock RAG + safety checks + multilingual output + FHIR write
   - fhir_sync.py — DynamoDB Streams → HealthLake FHIR write
   - budget_enforcer.py — progressive service degradation on budget breach

3. ECS container (Dockerfile + rppg_processor.py): CHROM algorithm, skin-tone adaptive preprocessing, Fitzpatrick scale handling, confidence scoring

4. Bedrock KB ingestion script: upload PDFs to S3, configure chunking + metadata tagging

5. Sample FHIR resources (JSON): Patient (national ID), Encounter (offline-origin tag), Observation (rPPG + confidence extensions), Observation (cough score), DiagnosticReport (TB screening + referral)

6. CloudWatch dashboard JSON (import-ready, all 8 panels)

7. CHW user guide (Markdown, bilingual): voice recording, camera vitals, cough samples, offline mode, triage interpretation, escalation protocol

8. Load test (Locust): 50 concurrent CHWs, mix (voice 60%, multimodal 25%, sync 10%, text 5%), assert P50<20s, P95<45s, EMERGENCY<3s

## WELL-ARCHITECTED ALIGNMENT

OPERATIONAL EXCELLENCE:
- CloudWatch dashboard with 8 panels for full observability
- CloudTrail audit logging on all FHIR operations
- Step Functions for orchestrated, observable workflows
- Progressive degradation (not hard failure) on budget limits
- DynamoDB TTL for automatic session cleanup

SECURITY:
- KMS CMK encryption at rest (HealthLake, S3, DynamoDB, Aurora)
- Cognito + SMART on FHIR authorization with role-based access
- WAF with rate limiting and geo-restriction
- VPC private subnets — no public endpoints
- VPC endpoints for all AWS service calls (no internet transit)
- PII masking in all logs via Bedrock Guardrails
- Presigned URLs with 3-minute expiry for uploads

RELIABILITY:
- Cross-region DR failover for Bedrock (Titan Text Lite fallback)
- Three-tier offline architecture (full → degraded → offline)
- Step Functions retry with exponential backoff
- SQS FIFO with deduplication for exactly-once processing
- ECS auto-scaling (min 0, max 10) for rPPG demand spikes

PERFORMANCE EFFICIENCY:
- Model routing by complexity (Haiku for fast, Sonnet for deep)
- EMERGENCY detection path optimized for < 3 second response
- S3 multipart upload with 256KB chunks for low bandwidth
- Aurora Serverless v2 scales 0.5-2 ACU based on RAG query load
- Parallel processing of 5 cough samples via Step Functions

COST OPTIMIZATION:
- $0.014 per encounter at scale (15,000/month)
- ECS Fargate scale-to-zero when no rPPG requests
- Aurora Serverless v2 scales to 0.5 ACU during idle
- Transcribe Standard ($0.024/min) not Medical ($0.075/min) — saves 68%
- Budget actions with progressive service degradation
- Reserved Lambda concurrency caps (max 50)

SUSTAINABILITY:
- Serverless-first (Lambda, Fargate, Aurora Serverless)
- Scale-to-zero on all compute when idle
- Reject oversized inputs early (audio > 3min, video > 50MB)
- Efficient RAG chunking reduces embedding compute

## AWS SERVICES (20+)

Compute: Lambda, ECS Fargate. AI/ML: Bedrock (Claude Sonnet/Haiku, Titan Embeddings), Transcribe, Rekognition. Storage: S3, DynamoDB, Aurora Serverless v2 (pgvector). Healthcare: HealthLake (FHIR R4). Integration: Step Functions, SQS FIFO, AppSync. Security: Cognito, KMS, WAF. Networking: VPC, VPC Endpoints, CloudFront. Monitoring: CloudWatch, CloudTrail, Budgets, SNS.

## REAL-WORLD IMPACT

Scale: 15K encounters/month on $215. 150K/month scales to ~$2,150. Supports 1,000+ concurrent CHWs.

Health impact: TB early detection (2-4 weeks earlier), maternal health (voice in local language), equity (skin-tone-aware rPPG), access (offline = 100% coverage in zero-connectivity areas).

Country deployments (configuration only — no code changes):
- Tanzania: sw-TZ, MoH STG 2023, NHIF formulary
- Rwanda: rw-RW, MOH clinical protocols, mutuelle coverage
- India: hi-IN + bn-IN, AYUSH guidelines, Jan Aushadhi drugs
- Indonesia: id-ID, Kemenkes protocols, BPJS formulary
- Nigeria: ha-NG, FMOH guidelines, NHIS coverage

## TROUBLESHOOTING

- HealthLake fails → Wrong region. Use us-east-1/us-east-2/us-west-2/ap-south-1/eu-west-1/eu-west-2/ap-southeast-2/ca-central-1.
- Transcribe garbage for non-English → Using Medical (en-US only). Switch to Standard. Check language code (sw-TZ not sw-KE).
- Bedrock "model not available" → Grant Claude access in console. Try cross-region fallback to Titan Text Lite.
- rPPG low confidence → Expected for Fitzpatrick V-VI. Verify skin-tone preprocessing. Increase clip to 30s.
- Offline not syncing → Check DynamoDB Streams enabled. Check fhir_sync Lambda logs. Verify sync_status GSI.
- Latency >45s → CloudWatch panel 4. Fargate cold start (min tasks=1), Aurora cold start (min ACU=1), Bedrock throttling.
- Budget exceeded → Budget actions have ~15min delay. Set threshold at 80%.
- Custom vocabulary not working → Check format (tab-separated: Phrase, SoundsLike, IPA, DisplayAs). UTF-8 encoding. Processing takes 10-15min.
