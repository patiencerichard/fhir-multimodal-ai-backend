# FHIR Multimodal Clinical AI Backend for Community Health Workers

> This prompt builds a complete FHIR R4 clinical AI backend for
> Community Health Workers in low-resource settings — voice triage
> in 100+ languages, camera-based vitals estimation, TB cough
> screening, and offline-first sync for areas with no connectivity.
> Estimated cost: ~$0.014 per clinical encounter at 15,000/month.

═══════════════════════════════════════════════════════════
INTRODUCTION
═══════════════════════════════════════════════════════════

Millions of Community Health Workers (CHWs) in Africa, South Asia,
and Southeast Asia conduct clinical triage with no decision support
tools — relying on memory, paper forms, and basic training. They
work in areas with no reliable internet, serve patients who speak
dozens of local languages, and use basic Android smartphones as
their only technology.

This prompt generates a complete, production-ready AWS backend that
gives CHWs an AI-powered triage assistant that:

  • Understands voice in 100+ languages (Swahili, Somali,
    Kinyarwanda, Hindi, Indonesian, and more) — no reading required
  • Estimates heart rate and SpO2 from the phone camera — no
    pulse oximeter needed
  • Screens for TB from cough audio recordings
  • Works fully offline with embedded IMCI rules, syncing to the
    cloud when connectivity returns
  • Costs ~$0.014 per encounter — affordable at national scale

The architecture is country-agnostic and language-pluggable.
All country-specific values (national ID URI, language codes,
clinical guidelines, drug formularies) are injected via
configuration — not hardcoded.

You are an AWS Solutions Architect and clinical systems engineer.
Build a production-ready, FHIR R4-compliant multimodal clinical AI
backend on AWS targeting low-resource health environments with
unreliable connectivity and multilingual patient populations.

═══════════════════════════════════════════════════════════
PREREQUISITES
═══════════════════════════════════════════════════════════

Before using this prompt, ensure:

1. AWS Account with Organizations enabled
2. AWS CLI v2 configured with AdministratorAccess 
   (or scoped deployment role)
3. Terraform >= 1.5 installed
4. Docker installed (for rPPG container build)
5. Python 3.11+ installed (for Lambda packaging)
6. The following AWS services enabled in your region:
   - Amazon HealthLake (check regional availability — 
     currently: us-east-1, us-east-2, us-west-2, 
     ap-south-1, eu-west-1, eu-west-2, ap-southeast-2,
     ca-central-1)
   - Amazon Bedrock with Claude model access granted
   - Amazon Transcribe (standard — NOT Medical, 
     which is en-US only)
7. Clinical guideline documents (PDF) ready for RAG ingestion:
   - Your country's Ministry of Health treatment guidelines
   - WHO IMCI guidelines
   - Any regional disease prevalence data
8. Custom vocabulary files for each target language
   (medical term mappings in Transcribe vocabulary format)

IMPORTANT REGIONAL NOTES:
- HealthLake is NOT available in af-south-1, me-south-1, 
  or most Asia-Pacific regions. Plan your primary region 
  accordingly. Available regions: us-east-1, us-east-2, 
  us-west-2, ap-south-1, eu-west-1, eu-west-2, 
  ap-southeast-2, ca-central-1.
- Amazon Transcribe Medical is en-US ONLY. For multilingual 
  voice intake, use Amazon Transcribe STANDARD which supports
  100+ languages including: sw-TZ (Swahili Tanzania), 
  so-SO (Somali), rw-RW (Kinyarwanda), fr-FR (French), 
  hi-IN (Hindi), bn-IN (Bengali), id-ID (Indonesian), 
  es-US (Spanish), pt-BR (Portuguese), and many more.
- STREAMING LIMITATION: Some languages (sw-TZ, rw-RW, bn-IN,
  sw-KE, sw-BI, sw-RW, sw-UG) support BATCH transcription 
  only — no real-time streaming. Design your voice pipeline 
  to use batch StartTranscriptionJob for these languages.
  Languages with streaming support (so-SO, fr-FR, hi-IN, 
  id-ID, es-US, pt-BR) can use real-time WebSocket streaming.
- Bedrock Claude availability varies by region. Confirm 
  model access before deployment. Use cross-region inference
  (Geo or Global) for higher throughput and availability.

═══════════════════════════════════════════════════════════
USE CASE
═══════════════════════════════════════════════════════════

WHO THIS IS FOR:
- Health-tech startups deploying AI triage in emerging markets
- NGOs digitizing community health worker programs
- Government health ministries building national digital health
- Developers building offline-first clinical apps
- Researchers prototyping multimodal health AI systems

WHAT PROBLEM THIS SOLVES:
Community health workers in low-resource settings lack clinical
decision support tools that work with:
- Low literacy populations (voice-first, not text-first)
- Local languages (not English-only)
- Unreliable connectivity (offline must work, not just online)
- Basic smartphones (no specialized medical devices)
- Tight budgets (~$0.01-0.02 per clinical encounter)

EXPECTED OUTCOME:
After running this prompt, you will have:
- Complete Terraform IaC for the entire backend
- 7 Lambda functions (Python 3.11) for the processing pipeline
- An ECS Fargate container for camera-based vitals estimation
- A Bedrock RAG knowledge base with clinical guidelines
- Sample FHIR R4 resources (Patient, Encounter, Observation, 
  DiagnosticReport)
- CloudWatch dashboard JSON (import-ready)
- A bilingual CHW user guide
- A Locust load test script
- Total infrastructure cost: ~$215/month for 15,000 encounters

DEPLOYMENT TIMELINE:
  Day 1:  terraform init && terraform apply (infrastructure)
  Day 2:  Upload clinical guidelines → trigger KB sync
  Day 3:  Deploy Lambda code + build rPPG container
  Day 4:  Configure Transcribe custom vocabularies per language
  Day 5:  Integration testing + load test (Locust)
  Total:  5 working days from AWS account to production-ready

COST COMPARISON vs ALTERNATIVES:
  ┌──────────────────────────┬──────────────┬──────────────────┐
  │ Approach                 │ Per Encounter │ 15K/month Total  │
  ├──────────────────────────┼──────────────┼──────────────────┤
  │ This prompt (AWS native) │ $0.014       │ $215             │
  │ OpenAI GPT-4 + Whisper   │ $0.08-0.12   │ $1,200-1,800     │
  │ Google Cloud Healthcare  │ $0.05-0.08   │ $750-1,200       │
  │ Custom on-prem servers   │ $0.03-0.05   │ $450-750 + ops   │
  └──────────────────────────┴──────────────┴──────────────────┘
  Key advantage: 85% cheaper than GPT-4 alternatives while 
  maintaining FHIR R4 compliance and offline capability.

═══════════════════════════════════════════════════════════
ARCHITECTURE SUMMARY
═══════════════════════════════════════════════════════════

  ┌─────────────────────────────────────────────────────┐
  │  CHW Android App (Flutter, offline-first)           │
  └────────────┬──────────────┬──────────────┬──────────┘
               │ Voice        │ Camera       │ Cough
               ▼              ▼              ▼
  ┌────────────────────────────────────────────────────┐
  │  LAYER 2 — Multimodal Intake Pipeline              │
  │  Path A: Transcribe Standard (100+ languages)      │
  │  Path B: ECS Fargate rPPG (CHROM algorithm)        │
  │  Path C: Step Functions + MFCC + Bedrock Haiku     │
  └────────────────────┬───────────────────────────────┘
                       ▼
  ┌────────────────────────────────────────────────────┐
  │  LAYER 3 — Clinical Reasoning (Bedrock Claude)     │
  │  RAG from Aurora pgvector knowledge base           │
  │  Multilingual output + safety guardrails           │
  └────────────────────┬───────────────────────────────┘
                       ▼
  ┌────────────────────────────────────────────────────┐
  │  LAYER 1 — HealthLake FHIR R4 Datastore            │
  │  KMS CMK · SMART on FHIR · CloudTrail audit        │
  └────────────────────────────────────────────────────┘
  ┌────────────────────────────────────────────────────┐
  │  LAYER 4 — Offline Sync (AppSync + DynamoDB)       │
  │  FULL → DEGRADED → OFFLINE tiers                   │
  └────────────────────────────────────────────────────┘
  ┌────────────────────────────────────────────────────┐
  │  LAYER 5 — Monitoring, Cost Controls, Compliance   │
  │  CloudWatch (8 panels) · Budgets · WAF · VPC       │
  └────────────────────────────────────────────────────┘

═══════════════════════════════════════════════════════════
LAYER 1 — PATIENT DATA FOUNDATION (FHIR R4)
═══════════════════════════════════════════════════════════

Deploy AWS HealthLake as the FHIR R4-compliant datastore:

- Resource types required: Patient, Observation, Condition, 
  Encounter, DiagnosticReport, MedicationRequest, Practitioner,
  Organization
- Enable SMART on FHIR authorization (Cognito + Lambda authorizer)
- Patient identity: National ID + facility code composite key
  stored as FHIR Identifier with system URI 
  "urn:{country_code}:moh:national-id"
  (configurable per deployment country)
- All Observations tagged with LOINC codes (mandatory):
  - Respiratory rate: LOINC 9279-1
  - SpO2: LOINC 59408-5
  - Temperature: LOINC 8310-5
  - Heart rate: LOINC 8867-4
  - Cough classification: custom extension 
    "{project}:cough-risk-score" (registered in local CodeSystem)
- HealthLake encryption: AWS KMS customer-managed key (CMK),
  automatic rotation every 365 days
- Audit logging: all FHIR read/write operations → CloudTrail → 
  S3 with 7-year retention (configurable per country's data 
  retention laws)
- Region: deploy in a region where HealthLake is available.
  Use a second HealthLake-available region for DR failover.
  IMPORTANT: HealthLake is NOT available in af-south-1.
  For data residency requirements, use KMS CMK controlled 
  by the local health authority + contractual data processing 
  agreements.
- Terraform resource: aws_healthlake_fhir_datastore

═══════════════════════════════════════════════════════════
LAYER 2 — MULTIMODAL INTAKE PIPELINE
═══════════════════════════════════════════════════════════

Build three parallel intake paths that converge at a single 
clinical reasoning Lambda:

--- PATH A: MULTILINGUAL VOICE INTAKE ---

CRITICAL: Use Amazon Transcribe STANDARD, NOT Transcribe Medical.
Transcribe Medical is en-US ONLY. Standard Transcribe natively 
supports 100+ languages at $0.024/min (cheaper than Medical 
at $0.075/min).

Configure your target languages based on deployment country.
Example language sets by region:

  East Africa: sw-TZ, sw-KE, so-SO, rw-RW, lg-IN, fr-FR, en-ZA
  South Asia:  hi-IN, bn-IN, ta-IN, en-IN
  Southeast Asia: id-ID, vi-VN, tl-PH, ms-MY, en-AU
  Latin America: es-US, pt-BR, en-US
  West Africa: ha-NG, wo-SN, fr-FR, en-ZA

Architecture:
  Mobile App → S3 (audio upload, presigned URL, 3min expiry)
  → S3 Event → SQS FIFO (dedup by encounter_id)
  → Lambda (transcription orchestrator)
    → Auto-detect language OR use CHW-selected language
    → Amazon Transcribe STANDARD with custom vocabulary 
      per language
  → Lambda (transcript cleaner + medical term normalizer)
    → Map local-language symptoms to SNOMED CT concepts 
      via Bedrock Haiku (fast structured extraction)
  → Clinical Reasoning Lambda

Configuration for Transcribe:
  - Language identification: ENABLED — auto-detect from 
    configured language pool when CHW does not specify
  - Custom vocabulary file per language: 
    s3://{project}-assets/vocab/{lang}-medical-vocab.txt
  - Example Swahili medical vocabulary:
    homa=fever, kikohozi=cough, upungufu wa pumzi=dyspnea,
    kifua kikuu=tuberculosis, damu=blood, maumivu=pain,
    kifafa=seizure, kuharisha=diarrhea, mjamzito=pregnant,
    dharura=emergency
  - MediaFormat: mp4 (Android default voice memo)
  - Custom vocabulary filter: mask profanities
  - Output: transcript JSON → DynamoDB session store (TTL: 2hr)

Cost control: Lambda pre-checks audio duration. 
  Reject if > 180 seconds. 
  Estimated cost: $0.024/min standard Transcribe, all languages.

--- PATH B: CAMERA-BASED VITALS (rPPG) ---

Architecture:
  Mobile camera stream (30fps, 15-second clip)
  → S3 multipart upload (chunked for low bandwidth, 256KB chunks)
  → Lambda (video validator: reject if < 720p, > 50MB, or < 10s)
  → Amazon Rekognition (face detection + lighting quality check)
  → ECS Fargate task (rPPG signal processor — Python, 
    custom container)
  → Results → FHIR Observation resources in HealthLake

rPPG Fargate Container spec:
  - Base image: python:3.11-slim
  - Libraries: opencv-python-headless, scipy, numpy
  - Algorithm: CHROM (chrominance-based rPPG) with 
    SKIN-TONE ADAPTIVE PREPROCESSING
  - Skin tone handling (critical for diverse populations):
    - Fitzpatrick I-IV: standard CHROM pipeline
    - Fitzpatrick V-VI: enhanced preprocessing 
      (adaptive ROI, green-channel emphasis, extended signal 
      averaging) + REDUCED confidence ceiling (max = "moderate")
    - Skin tone estimated from Rekognition face attributes
  - Outputs: estimated HR with confidence interval,
    estimated SpO2 proxy with confidence interval
    (report actual confidence — not fixed accuracy claims)
  - Runtime: ~8 seconds per 15-second clip on 0.5 vCPU / 1GB
  - Auto-scale: ECS Service with target tracking (CPU 70%), 
    min 0 tasks, max 10 tasks
  - FHIR write: Lambda posts Observation resources to HealthLake
    immediately after rPPG completes

CRITICAL: All rPPG-derived values MUST be flagged in FHIR with:
  Observation.status = "preliminary"
  Observation.note = "Estimated via rPPG camera analysis. 
    NOT a medical device measurement. Requires clinical 
    confirmation with pulse oximeter before treatment decisions."
  Extension "{project}:measurement-confidence" = low|moderate|high
  Extension "{project}:skin-tone-flag" = standard|reduced-confidence

ETHICAL NOTE: rPPG literature documents significant accuracy 
degradation for darker skin tones (Fitzpatrick V-VI). Mitigations:
  1. Explicit confidence scoring per measurement
  2. Never use rPPG SpO2 alone for clinical decisions
  3. Always recommend physical pulse oximeter confirmation
  4. Monitor accuracy distribution by skin tone in CloudWatch

--- PATH C: COUGH AUDIO TB SCREENING ---

Architecture:
  CHW records 5 cough samples via app
  → S3 upload (individual .wav files, ~3-second clips each)
  → Step Functions workflow (parallel processing of 5 samples)
  → Lambda per sample: feature extraction 
    (MFCCs via scipy — 13 coefficients)
  → Lambda: aggregate features → Bedrock InvokeModel
    (Claude Haiku — rapid classification)
  → Risk score 0-100 → DynamoDB + FHIR DiagnosticReport

Bedrock prompt for cough classification (inject MFCC values):
  "You are a clinical audio analysis assistant supporting 
  respiratory disease screening. Given MFCC summary statistics 
  extracted from patient cough recordings, assess the likelihood 
  of TB-pattern cough versus common respiratory illness.

  IMPORTANT: This is a SCREENING tool, not a diagnostic. Your 
  output helps prioritize patients for confirmatory testing 
  (e.g., GeneXpert, sputum smear, chest X-ray).

  MFCC data: {mfcc_summary}. 
  Patient context: age {age}, sex {sex}, HIV status {hiv_status}, 
  prior TB history {tb_history}, region {region}.
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

Step Functions error handling:
  - If < 3 of 5 samples succeed: mark result as INSUFFICIENT_DATA,
    request re-recording
  - Retry policy: 2 retries, exponential backoff (30s base)
  - On failure: fallback to symptom-only triage

═══════════════════════════════════════════════════════════
LAYER 3 — CLINICAL REASONING ENGINE (Amazon Bedrock)
═══════════════════════════════════════════════════════════

Model selection and routing:
  - Full triage encounter: Claude Sonnet (claude-sonnet-4-20250514)
    — best clinical reasoning + multilingual output
  - Cough classification + quick checks: Claude Haiku
    — speed + cost for structured tasks
  - EMERGENCY detection: Claude Haiku 
    — latency-critical, must respond < 3 seconds
  - Complex/rare cases: Claude Sonnet with extended context
    — pregnancy, pediatric < 2y, multi-morbidity
  - Fallback: Titan Text Lite if Sonnet unavailable 
    (cross-region failover)

Bedrock Knowledge Base (RAG) configuration:
  - Source: S3 bucket "{project}-clinical-knowledge"
    Documents: 
      Country MoH treatment guidelines (PDF),
      WHO IMCI guidelines (PDF),
      MSF Clinical Guide (PDF),
      Regional disease prevalence data,
      National essential medicines list
  - Embedding model: Titan Embeddings V2
  - Vector store: Aurora Serverless v2 + pgvector 
    (db.serverless, 0.5-2 ACU)
  - Chunking: 512 tokens, 20% overlap
  - Metadata filters: document_type, region, disease_category,
    patient_age_group
  - Max retrieved chunks: 5 per query

Master clinical reasoning prompt (inject per encounter):
  "You are a clinical decision support AI for community health 
  workers. You ASSIST — you do NOT replace — licensed clinicians. 
  Your role is to synthesize patient data into a structured 
  triage recommendation.

  PATIENT DATA:
  - Symptoms (original language: {source_language}): 
    {transcript_original}
  - Symptoms (English translation): {transcript_english}
  - rPPG vitals (PRELIMINARY — camera-estimated, NOT 
    device-measured):
    HR {heart_rate} bpm (confidence: {hr_confidence}),
    SpO2 {spo2}% (confidence: {spo2_confidence})
  - Cough screening score: {cough_risk_score}/100 ({risk_tier})
  - Age: {age}, Sex: {sex}, Pregnancy status: {pregnancy}
  - Known conditions: {conditions}
  - Current medications: {medications}
  - Allergies: {allergies}
  - Facility location: {district}, {region}
  - Retrieved clinical guidelines: {rag_context}

  INSTRUCTIONS:
  1. Identify top 3 differential diagnoses with reasoning
  2. Assign triage category: EMERGENCY / URGENT / ROUTINE / 
     SELF-CARE
  3. List immediate actions the CHW should take NOW
  4. State clearly what requires a physician — never exceed 
     CHW scope
  5. If TB risk > 60 OR SpO2 < 94%: ALWAYS recommend facility 
     referral
  6. If chest pain + dyspnea + age > 35: ALWAYS mark EMERGENCY
  7. Respond in BOTH English AND the patient's source language 
     ({source_language})
  8. Flag any drug interactions against medications AND allergies
  9. Reference retrieved clinical guidelines where applicable
  10. Include available free/subsidized government medications 
      in recommendations where appropriate

  CRITICAL SAFETY RULES:
  - NEVER diagnose. Use: 'suggests', 'consistent with', 
    'warrants evaluation for'
  - NEVER recommend prescription medications or dosages
  - NEVER provide mental health crisis intervention — route 
    to specialist
  - NEVER recommend surgical procedures
  - If uncertain: ESCALATE. Never guess.
  - All rPPG vitals are PRELIMINARY — always recommend device 
    confirmation
  - Drug allergy cross-reactivity: penicillin allergy → flag 
    ALL beta-lactams

  Return structured JSON:
  {
    'triage_category': 'EMERGENCY|URGENT|ROUTINE|SELF_CARE',
    'differentials': [...],
    'chw_actions': [...],
    'physician_referral_reasons': [...],
    'drug_interactions': [...],
    'response_english': '...',
    'response_local_language': '...',
    'response_language_code': '{source_language}',
    'guidelines_cited': [...],
    'confidence': 'low|medium|high'
  }"

Bedrock Guardrails (mandatory):
  - Content filter: BLOCK medical misinformation
  - Grounding: ENABLED (responses must cite retrieved guidelines)
  - PII detection: mask patient names in all logs
  - Denied topics: prescription drug dosing, surgical procedures,
    mental health crisis intervention (route to specialist)
  - Word policy: block "diagnose", "prescription", 
    "you have [disease]"

Latency targets:
  - Full triage (all 3 paths): < 45 seconds end-to-end
  - Quick symptom check (voice only): < 15 seconds
  - EMERGENCY detection: < 3 seconds

═══════════════════════════════════════════════════════════
LAYER 4 — OFFLINE-FIRST SYNC (Rural Clinic Mode)
═══════════════════════════════════════════════════════════

Three connectivity tiers:
  FULL     — stable internet: all 3 intake paths active, 
             real-time Bedrock reasoning
  DEGRADED — intermittent/slow: voice + text only 
             (no video upload), queue for sync
  OFFLINE  — no connectivity: rule-based IMCI triage from 
             embedded JSON, local storage only

Mobile app (Flutter):
  - SQLite local cache: stores up to 200 patient encounters
  - Hive encrypted storage: clinical data at rest (AES-256)
  - Offline triage: rule-based fallback (IMCI decision tree,
    embedded as JSON in app bundle)
  - Queue: all data tagged with sync_status: PENDING
  - Offline triage clearly marked in UI: "This recommendation 
    was generated OFFLINE using basic rules. Seek cloud-assisted 
    triage when connectivity is restored."

AWS sync infrastructure:
  - AppSync (GraphQL) with DynamoDB conflict resolution
  - DynamoDB Streams → Lambda → HealthLake FHIR write
    (eventual consistency acknowledged in FHIR resource metadata:
    meta.tag = "offline-origin")
  - Sync trigger: on connectivity restored OR manual CHW action
  - Conflict resolution: 
    - Vitals/observations: last-writer-wins 
      (most recent measurement is most relevant)
    - Clinical notes/assessments: manual review queue 
      (DynamoDB GSI: conflict_flag = true)
    - Patient demographics: server-wins 
      (prevent offline edits from overwriting verified data)
  - CloudFront + S3: cache clinical guidelines locally 
    (offline reference materials, updated weekly)

═══════════════════════════════════════════════════════════
LAYER 5 — MONITORING, COST CONTROLS & COMPLIANCE
═══════════════════════════════════════════════════════════

CloudWatch Dashboard — 8 panels required:
  1. Triage volume by channel (voice/rPPG/cough) — 1hr rolling
  2. Triage volume by language — 1hr rolling
  3. Bedrock token consumption + estimated cost — daily
  4. Average triage latency P50/P95 — 5min resolution
  5. Offline encounter queue depth (DynamoDB item count)
  6. FHIR write errors (HealthLake 4xx/5xx) — alarm if >1%
  7. rPPG Fargate task duration — alarm if >60s avg
  8. rPPG confidence distribution by skin tone — daily 
     (equity monitoring)

Cost controls:
  - AWS Budgets: configurable hard limit (default $300/month)
  - Budget action → SNS → Lambda → progressive degradation:
    1. First: disable rPPG path (most expensive)
    2. Then: disable cough screening
    3. Last resort: route all to Haiku 
       (NEVER disable voice triage — cheapest and most critical)
  - Bedrock per-invoke cost check: if estimated tokens > 2000,
    route to Haiku not Sonnet
  - Transcribe: reject audio > 3 minutes
  - Reserved concurrency on clinical Lambda: max 50 
    (prevent runaway costs)

Estimated monthly cost at 500 daily encounters (15,000/month):
  - Bedrock (Sonnet + Haiku mixed): ~$85
  - Amazon Transcribe (standard):   ~$40
  - HealthLake:                     ~$35
  - ECS Fargate (rPPG, scale-to-0): ~$25
  - Aurora Serverless v2 (pgvector): ~$30
  - Total: ~$215/month
  - Per-encounter cost: ~$0.014

Compliance (configure per country):
  - Primary region: choose a HealthLake-available region
  - DR region: choose a second HealthLake-available region
  - KMS CMK rotation: enabled, 365-day schedule
  - VPC: HealthLake + Aurora in private subnets only
  - No public endpoints: API Gateway with WAF + Cognito only
  - WAF: rate limiting 100 req/IP/min, geo-restriction to 
    deployment country IPs + admin allowlist
  - CloudTrail: all management + data events, encrypted, 
    retention period per local law (default 7 years)
  - Data residency: where HealthLake is not available locally,
    use KMS CMK held by local health authority + contractual 
    data processing agreements

═══════════════════════════════════════════════════════════
REQUIRED OUTPUTS
═══════════════════════════════════════════════════════════

Generate ALL of the following:

1. Terraform (HCL) — complete infrastructure:
  - HealthLake FHIR datastore + KMS CMK
  - Cognito User Pool (roles: CHW_BASIC, NURSE, PHYSICIAN, ADMIN)
  - S3 buckets (audio, video, knowledge base, audit logs — 
    separate lifecycle policies per bucket)
  - SQS FIFO queues (audio intake, cough samples, sync queue)
  - Step Functions state machine (cough screening workflow)
  - ECS cluster + Fargate task definition (rPPG container, 
    scale-to-zero)
  - Aurora Serverless v2 cluster + pgvector extension (0.5-2 ACU)
  - Bedrock Knowledge Base + S3 data source
  - AppSync GraphQL API + DynamoDB tables 
    (sessions, sync queue, conflicts)
  - CloudWatch dashboard + alarms + Budget + SNS topics
  - WAF WebACL (rate limiting + geo-restriction)
  - VPC + private subnets + VPC endpoints 
    (Bedrock, S3, DynamoDB, HealthLake)
  - IAM roles with least-privilege policies per Lambda function

2. Lambda functions (Python 3.11):
  - channel_router.py — detect input type (voice/video/cough/
    text), validate, route to correct pipeline
  - transcription_orchestrator.py — invoke Transcribe STANDARD 
    with language detection, apply custom vocabulary, clean 
    transcript, map medical terms via Haiku
  - rppg_result_handler.py — receive Fargate results, apply 
    confidence scoring + skin-tone flag, write FHIR Observation
  - cough_feature_extractor.py — MFCC extraction 
    (13 coefficients via scipy)
  - clinical_reasoning.py — Bedrock invoke with RAG retrieval, 
    safety checks, multilingual output, FHIR Encounter + 
    DiagnosticReport write
  - fhir_sync.py — DynamoDB Streams trigger → transform offline 
    encounters → HealthLake FHIR write
  - budget_enforcer.py — progressive service degradation on 
    budget threshold breach

3. ECS container (Dockerfile + rppg_processor.py):
  — CHROM algorithm with skin-tone adaptive preprocessing
  — Confidence scoring per measurement
  — Fitzpatrick scale handling

4. Bedrock Knowledge Base ingestion script:
  — Upload clinical guideline PDFs to S3
  — Configure chunking, metadata tagging, and index build

5. Sample FHIR resources (JSON):
  - Patient (with configurable national ID identifier)
  - Encounter (multilingual, with offline-origin tag)
  - Observation: rPPG vitals with confidence extensions + 
    skin-tone flag
  - Observation: cough risk score
  - DiagnosticReport: TB screening result with referral

6. CloudWatch dashboard JSON (import-ready, all 8 panels)

7. CHW user guide (Markdown, bilingual template):
  — How to record voice symptoms (any supported language)
  — How to capture camera vitals (lighting, face positioning)
  — How to record cough samples (5 samples, technique)
  — What to do when offline (IMCI triage, sync later)
  — How to interpret triage outputs (EMERGENCY → call 
    local emergency number)
  — Escalation protocol (when to refer, where to refer)

8. Load test script (Locust — Python):
  — Simulate 50 concurrent CHW sessions
  — Mix: voice-only 60%, full multimodal 25%, 
    offline sync 10%, text-only 5%
  — Configurable language distribution
  — Assert latency SLOs: P50 < 20s, P95 < 45s, EMERGENCY < 3s

═══════════════════════════════════════════════════════════
AWS WELL-ARCHITECTED FRAMEWORK ALIGNMENT
═══════════════════════════════════════════════════════════

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
  - Conflict resolution strategies per data type on sync

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
  - Transcribe Standard ($0.024/min) not Medical ($0.075/min)
  - Haiku for structured tasks, Sonnet only for full reasoning
  - Budget actions with progressive service degradation
  - Reserved Lambda concurrency caps (max 50)

SUSTAINABILITY:
  - Serverless-first (Lambda, Fargate, Aurora Serverless)
  - Scale-to-zero on all compute when idle
  - Reject oversized inputs early (audio > 3min, video > 50MB)
  - Efficient RAG chunking reduces embedding compute

═══════════════════════════════════════════════════════════
AWS SERVICES USED
═══════════════════════════════════════════════════════════

Compute:      AWS Lambda, Amazon ECS Fargate
AI/ML:        Amazon Bedrock (Claude Sonnet, Haiku, Titan), 
              Amazon Transcribe, Amazon Rekognition
Storage:      Amazon S3, Amazon DynamoDB, Amazon Aurora 
              Serverless v2 (pgvector)
Healthcare:   AWS HealthLake (FHIR R4)
Integration:  AWS Step Functions, Amazon SQS FIFO, 
              AWS AppSync (GraphQL)
Security:     Amazon Cognito, AWS KMS, AWS WAF
Networking:   Amazon VPC, VPC Endpoints, Amazon CloudFront
Monitoring:   Amazon CloudWatch, AWS CloudTrail, 
              AWS Budgets, Amazon SNS

═══════════════════════════════════════════════════════════
REAL-WORLD IMPACT & SCALE
═══════════════════════════════════════════════════════════

This architecture is designed for national-scale deployment:

SCALE TARGETS:
  - 15,000 encounters/month (500/day) on $215/month
  - 150,000 encounters/month scales linearly to ~$2,150/month
  - Supports 1,000+ concurrent CHWs across multiple facilities

HEALTH IMPACT POTENTIAL:
  - TB early detection: cough screening catches cases 2-4 weeks 
    earlier than symptom-only triage, improving treatment outcomes
  - Maternal health: voice triage in local language enables 
    pregnant women to describe danger signs without literacy
  - Equity: skin-tone-aware rPPG prevents systematic bias in 
    vitals estimation for darker-skinned populations
  - Access: offline mode ensures 100% coverage even in areas 
    with zero connectivity (estimated 40% of rural clinics)

COUNTRY DEPLOYMENTS (configuration only — no code changes):
  - Tanzania: sw-TZ, MoH STG 2023, NHIF formulary
  - Rwanda: rw-RW, MOH clinical protocols, mutuelle coverage
  - India: hi-IN + bn-IN, AYUSH guidelines, Jan Aushadhi drugs
  - Indonesia: id-ID, Kemenkes protocols, BPJS formulary
  - Nigeria: ha-NG, FMOH guidelines, NHIS coverage

═══════════════════════════════════════════════════════════
TROUBLESHOOTING
═══════════════════════════════════════════════════════════

PROBLEM: HealthLake creation fails
  → Check region. HealthLake only available in: us-east-1, 
    us-east-2, us-west-2, ap-south-1, eu-west-1, eu-west-2, 
    ap-southeast-2, ca-central-1. NOT available in af-south-1.

PROBLEM: Transcribe returns empty/garbage for non-English audio
  → Verify you are using Transcribe STANDARD, not Medical.
    Medical is en-US only. Check language code matches your 
    audio (e.g., sw-TZ not sw-KE for Tanzania Swahili).

PROBLEM: Bedrock returns "model not available" 
  → Confirm Claude model access is granted in your region via 
    Bedrock console → Model access. Try cross-region fallback 
    to Titan Text Lite.

PROBLEM: rPPG returns low confidence for most patients
  → Expected for Fitzpatrick V-VI skin tones. Verify 
    skin-tone adaptive preprocessing is enabled. Check 
    lighting conditions in CHW training materials. Consider 
    increasing clip duration from 15s to 30s for better signal.

PROBLEM: Offline encounters not syncing
  → Check AppSync connection status. Verify DynamoDB Streams 
    are enabled. Check Lambda fhir_sync.py CloudWatch logs 
    for HealthLake write errors. Verify sync_status GSI exists.

PROBLEM: Triage latency exceeds 45 seconds
  → Check which path is slow (CloudWatch panel 4). Common 
    causes: Fargate cold start (increase min tasks to 1), 
    Aurora cold start (increase min ACU to 1), Bedrock 
    throttling (check service quotas).

PROBLEM: Budget exceeded despite controls
  → Check budget_enforcer Lambda logs. Verify SNS topic 
    subscription is confirmed. Budget actions have ~15 min 
    delay. Set budget threshold at 80% to trigger early.

PROBLEM: Custom vocabulary not improving transcription
  → Verify vocabulary file format matches Transcribe spec 
    (tab-separated: Phrase, SoundsLike, IPA, DisplayAs).
    Check file encoding is UTF-8. Vocabulary processing 
    can take 10-15 minutes after upload.