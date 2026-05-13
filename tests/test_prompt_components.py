"""Comprehensive component tests for the fhir-multimodal-ai-backend prompt.

Validates every major claim, section, and deliverable in prompt.md
to ensure the submission is competition-ready for AWS Prompt the Planet.

Run with:
    .venv/bin/pytest tests/test_prompt_components.py -v
"""
import json
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read_file(rel_path):
    with open(os.path.join(ROOT, rel_path)) as f:
        return f.read()


# ===========================================================================
# 1. PROMPT CONTENT VALIDATION
# ===========================================================================
class TestPromptStructure(unittest.TestCase):
    """Verify prompt.md has all required sections and claims."""

    @classmethod
    def setUpClass(cls):
        cls.prompt = read_file("prompt.md")

    def test_has_all_major_sections(self):
        required = [
            "INTRODUCTION", "PREREQUISITES", "USE CASE",
            "ARCHITECTURE SUMMARY", "LAYER 1", "LAYER 2",
            "LAYER 3", "LAYER 4", "LAYER 5",
            "REQUIRED OUTPUTS", "WELL-ARCHITECTED",
            "AWS SERVICES USED", "TROUBLESHOOTING",
        ]
        for section in required:
            self.assertIn(section, self.prompt, f"Missing section: {section}")

    def test_has_cost_estimate(self):
        self.assertIn("$0.014", self.prompt)
        self.assertIn("$215/month", self.prompt)

    def test_has_all_five_layers(self):
        for i in range(1, 6):
            self.assertIn(f"LAYER {i}", self.prompt)

    def test_has_seven_lambda_functions(self):
        lambdas = [
            "channel_router", "transcription_orchestrator",
            "rppg_result_handler", "cough_feature_extractor",
            "clinical_reasoning", "fhir_sync", "budget_enforcer",
        ]
        for fn in lambdas:
            self.assertIn(fn, self.prompt, f"Missing Lambda: {fn}")

    def test_has_eight_cloudwatch_panels(self):
        self.assertIn("8 panels", self.prompt)

    def test_has_safety_guardrails(self):
        safety_terms = [
            "NEVER diagnose", "NEVER recommend prescription",
            "NOT a medical device", "ASSIST", "NOT replace",
        ]
        for term in safety_terms:
            self.assertIn(term, self.prompt, f"Missing safety: {term}")

    def test_has_offline_tiers(self):
        for tier in ("FULL", "DEGRADED", "OFFLINE"):
            self.assertIn(tier, self.prompt)

    def test_has_well_architected_pillars(self):
        pillars = [
            "OPERATIONAL EXCELLENCE", "SECURITY", "RELIABILITY",
            "PERFORMANCE EFFICIENCY", "COST OPTIMIZATION", "SUSTAINABILITY",
        ]
        for p in pillars:
            self.assertIn(p, self.prompt, f"Missing pillar: {p}")


# ===========================================================================
# 2. REGIONAL ACCURACY
# ===========================================================================
class TestRegionalAccuracy(unittest.TestCase):
    """Verify all regional claims match AWS documentation."""

    @classmethod
    def setUpClass(cls):
        cls.prompt = read_file("prompt.md")

    def test_healthlake_regions_listed(self):
        expected = [
            "us-east-1", "us-east-2", "us-west-2",
            "ap-south-1", "eu-west-1", "eu-west-2",
            "ap-southeast-2", "ca-central-1",
        ]
        for region in expected:
            self.assertIn(region, self.prompt, f"Missing HealthLake region: {region}")

    def test_healthlake_excluded_regions(self):
        self.assertIn("af-south-1", self.prompt)
        self.assertIn("me-south-1", self.prompt)
        self.assertIn("NOT available", self.prompt)

    def test_transcribe_medical_en_us_only(self):
        self.assertIn("en-US ONLY", self.prompt)
        self.assertIn("Transcribe Medical", self.prompt)

    def test_transcribe_standard_languages(self):
        languages = ["sw-TZ", "so-SO", "rw-RW", "fr-FR", "hi-IN", "bn-IN", "id-ID", "es-US", "pt-BR"]
        for lang in languages:
            self.assertIn(lang, self.prompt, f"Missing language: {lang}")

    def test_streaming_limitation_documented(self):
        self.assertIn("STREAMING LIMITATION", self.prompt)
        self.assertIn("batch", self.prompt.lower())

    def test_bedrock_cross_region_noted(self):
        self.assertIn("cross-region", self.prompt.lower())

    def test_transcribe_standard_not_medical(self):
        # Verify the prompt explicitly says to use Standard
        self.assertIn("Transcribe STANDARD, NOT Transcribe Medical", self.prompt)


# ===========================================================================
# 3. FHIR SAMPLE COMPLIANCE
# ===========================================================================
class TestFhirSamples(unittest.TestCase):
    """Validate FHIR R4 sample resources match prompt claims."""

    def _load(self, name):
        return json.loads(read_file(f"fhir-samples/{name}"))

    def test_patient_has_national_id_identifier(self):
        p = self._load("patient.json")
        self.assertEqual(p["resourceType"], "Patient")
        ids = p["identifier"]
        self.assertTrue(any("moh:national-id" in i["system"] for i in ids))

    def test_encounter_has_offline_origin_tag(self):
        e = self._load("encounter.json")
        self.assertEqual(e["resourceType"], "Encounter")
        tags = e["meta"]["tag"]
        self.assertTrue(any(t["code"] == "offline-origin" for t in tags))

    def test_observation_rppg_is_preliminary(self):
        o = self._load("observation-rppg.json")
        self.assertEqual(o["status"], "preliminary")

    def test_observation_rppg_has_loinc_code(self):
        o = self._load("observation-rppg.json")
        codes = [c["code"] for c in o["code"]["coding"]]
        # Heart rate LOINC 8867-4
        self.assertIn("8867-4", codes)

    def test_observation_rppg_has_disclaimer_note(self):
        o = self._load("observation-rppg.json")
        notes = " ".join(n["text"] for n in o["note"])
        self.assertIn("NOT a medical device", notes)
        self.assertIn("rPPG", notes)

    def test_observation_rppg_has_confidence_extension(self):
        o = self._load("observation-rppg.json")
        urls = [e["url"] for e in o["extension"]]
        self.assertIn("measurement-confidence", urls)
        self.assertIn("skin-tone-flag", urls)

    def test_diagnostic_report_tb_has_referral(self):
        d = self._load("diagnostic-report-tb.json")
        self.assertEqual(d["resourceType"], "DiagnosticReport")
        self.assertEqual(d["status"], "preliminary")
        urls = [e["url"] for e in d["extension"]]
        self.assertIn("cough-risk-score", urls)
        self.assertIn("suggested-test", urls)

    def test_all_samples_have_resource_type(self):
        samples = ["patient.json", "encounter.json", "observation-rppg.json",
                   "observation-cough.json", "diagnostic-report-tb.json"]
        for s in samples:
            data = self._load(s)
            self.assertIn("resourceType", data, f"{s} missing resourceType")


# ===========================================================================
# 4. TERRAFORM STRUCTURE VALIDATION
# ===========================================================================
class TestTerraformStructure(unittest.TestCase):
    """Validate Terraform IaC matches prompt's REQUIRED OUTPUTS."""

    @classmethod
    def setUpClass(cls):
        cls.tf = read_file("terraform/main.tf")

    def test_has_healthlake_datastore(self):
        self.assertIn("aws_healthlake_fhir_datastore", self.tf)

    def test_has_kms_cmk_with_rotation(self):
        self.assertIn("aws_kms_key", self.tf)
        self.assertIn("enable_key_rotation", self.tf)

    def test_has_cognito_with_roles(self):
        self.assertIn("aws_cognito_user_pool", self.tf)
        for role in ("CHW_BASIC", "NURSE", "PHYSICIAN", "ADMIN"):
            self.assertIn(role, self.tf, f"Missing Cognito role: {role}")

    def test_has_s3_buckets(self):
        for bucket in ("audio", "video", "knowledge", "audit"):
            self.assertIn(f'"{bucket}"' if bucket != "knowledge" else "clinical-knowledge", self.tf)

    def test_has_sqs_fifo_queues(self):
        self.assertIn("fifo_queue", self.tf)
        self.assertIn("content_based_deduplication", self.tf)

    def test_has_ecs_fargate_rppg(self):
        self.assertIn("aws_ecs_cluster", self.tf)
        self.assertIn("aws_ecs_task_definition", self.tf)
        self.assertIn("FARGATE", self.tf)

    def test_has_aurora_serverless_pgvector(self):
        self.assertIn("aurora-postgresql", self.tf)
        self.assertIn("serverlessv2_scaling_configuration", self.tf)
        self.assertIn("min_capacity = 0.5", self.tf)
        self.assertIn("max_capacity = 2", self.tf)

    def test_has_bedrock_knowledge_base(self):
        self.assertIn("aws_bedrockagent_knowledge_base", self.tf)
        self.assertIn("titan-embed-text-v2", self.tf)
        self.assertIn("max_tokens = 512", self.tf)
        self.assertIn("overlap_percentage = 20", self.tf)

    def test_has_appsync_graphql(self):
        self.assertIn("aws_appsync_graphql_api", self.tf)

    def test_has_dynamodb_tables(self):
        self.assertIn("sessions", self.tf)
        self.assertIn("sync-queue", self.tf)
        self.assertIn("conflicts", self.tf)

    def test_has_cloudwatch_dashboard(self):
        self.assertIn("aws_cloudwatch_dashboard", self.tf)

    def test_has_waf_with_rate_limiting(self):
        self.assertIn("aws_wafv2_web_acl", self.tf)
        self.assertIn("rate_based_statement", self.tf)
        self.assertIn("limit", self.tf)

    def test_has_vpc_private_subnets(self):
        self.assertIn("aws_vpc", self.tf)
        self.assertIn("aws_subnet", self.tf)
        self.assertIn("private", self.tf)

    def test_has_vpc_endpoints(self):
        self.assertIn("aws_vpc_endpoint", self.tf)
        self.assertIn("bedrock-runtime", self.tf)

    def test_has_cloudtrail(self):
        self.assertIn("aws_cloudtrail", self.tf)
        self.assertIn("enable_log_file_validation", self.tf)

    def test_has_budget_with_thresholds(self):
        self.assertIn("aws_budgets_budget", self.tf)
        for threshold in ("80", "90", "100"):
            self.assertIn(f"threshold                  = {threshold}", self.tf)

    def test_has_all_seven_lambdas(self):
        lambdas = [
            "channel_router", "transcription_orchestrator",
            "rppg_result_handler", "cough_feature_extractor",
            "clinical_reasoning", "fhir_sync", "budget_enforcer",
        ]
        for fn in lambdas:
            self.assertIn(fn, self.tf, f"Missing Lambda in TF: {fn}")

    def test_clinical_reasoning_has_reserved_concurrency(self):
        self.assertIn("reserved_concurrent_executions", self.tf)
        self.assertIn("50", self.tf)

    def test_ecs_autoscaling(self):
        self.assertIn("aws_appautoscaling_target", self.tf)
        self.assertIn("max_capacity       = 10", self.tf)
        self.assertIn("min_capacity       = 0", self.tf)

    def test_s3_encryption(self):
        self.assertIn("aws_s3_bucket_server_side_encryption_configuration", self.tf)
        self.assertIn("aws:kms", self.tf)

    def test_dynamodb_streams_enabled(self):
        self.assertIn("stream_enabled   = true", self.tf)
        self.assertIn("NEW_IMAGE", self.tf)


# ===========================================================================
# 5. CLOUDWATCH DASHBOARD VALIDATION
# ===========================================================================
class TestCloudWatchDashboard(unittest.TestCase):
    """Validate dashboard JSON has all 8 required panels."""

    @classmethod
    def setUpClass(cls):
        cls.dashboard = json.loads(read_file("cloudwatch-dashboard.json"))

    def test_has_eight_widgets(self):
        self.assertEqual(len(self.dashboard["widgets"]), 8)

    def test_panel_titles_match_prompt(self):
        titles = [w["properties"]["title"] for w in self.dashboard["widgets"]]
        expected_keywords = [
            "Channel", "Language", "Token", "Latency",
            "Queue", "FHIR", "rPPG", "Skin Tone",
        ]
        for kw in expected_keywords:
            self.assertTrue(
                any(kw.lower() in t.lower() for t in titles),
                f"No panel with keyword: {kw}"
            )

    def test_latency_panel_has_slo_annotations(self):
        latency_widget = None
        for w in self.dashboard["widgets"]:
            if "Latency" in w["properties"]["title"]:
                latency_widget = w
                break
        self.assertIsNotNone(latency_widget)
        annotations = latency_widget["properties"]["annotations"]["horizontal"]
        values = [a["value"] for a in annotations]
        self.assertIn(20000, values)  # P50 SLO 20s
        self.assertIn(45000, values)  # P95 SLO 45s

    def test_equity_monitoring_panel_exists(self):
        found = False
        for w in self.dashboard["widgets"]:
            if "Skin Tone" in w["properties"]["title"]:
                found = True
                metrics = w["properties"]["metrics"]
                skin_tones = [m[3] for m in metrics]
                self.assertIn("ITA1-2", skin_tones)
                self.assertIn("ITA5-6", skin_tones)
        self.assertTrue(found, "Missing equity monitoring panel")


# ===========================================================================
# 6. ARCHITECTURE COMPLETENESS
# ===========================================================================
class TestArchitectureCompleteness(unittest.TestCase):
    """Verify all required outputs from prompt exist as files."""

    def test_all_lambda_files_exist(self):
        lambdas = [
            "channel_router.py", "transcription_orchestrator.py",
            "rppg_result_handler.py", "cough_feature_extractor.py",
            "clinical_reasoning.py", "fhir_sync.py", "budget_enforcer.py",
        ]
        for fn in lambdas:
            path = os.path.join(ROOT, "lambda", fn)
            self.assertTrue(os.path.exists(path), f"Missing: lambda/{fn}")

    def test_terraform_files_exist(self):
        for f in ("main.tf", "variables.tf", "terraform.tfvars.example"):
            path = os.path.join(ROOT, "terraform", f)
            self.assertTrue(os.path.exists(path), f"Missing: terraform/{f}")

    def test_container_files_exist(self):
        for f in ("Dockerfile", "rppg_processor.py"):
            path = os.path.join(ROOT, "container", f)
            self.assertTrue(os.path.exists(path), f"Missing: container/{f}")

    def test_fhir_samples_exist(self):
        expected = ["patient.json", "encounter.json", "observation-rppg.json",
                    "observation-cough.json", "diagnostic-report-tb.json"]
        for f in expected:
            path = os.path.join(ROOT, "fhir-samples", f)
            self.assertTrue(os.path.exists(path), f"Missing: fhir-samples/{f}")

    def test_cloudwatch_dashboard_exists(self):
        self.assertTrue(os.path.exists(os.path.join(ROOT, "cloudwatch-dashboard.json")))

    def test_chw_user_guide_exists(self):
        self.assertTrue(os.path.exists(os.path.join(ROOT, "docs", "chw-user-guide.md")))

    def test_load_test_exists(self):
        self.assertTrue(os.path.exists(os.path.join(ROOT, "tests", "load_test.py")))

    def test_knowledge_base_script_exists(self):
        self.assertTrue(os.path.exists(os.path.join(ROOT, "scripts", "ingest_knowledge_base.py")))


# ===========================================================================
# 7. SUBMISSION.md VALIDATION
# ===========================================================================
class TestSubmission(unittest.TestCase):
    """Validate SUBMISSION.md matches competition requirements."""

    @classmethod
    def setUpClass(cls):
        cls.sub = read_file("SUBMISSION.md")

    def test_has_title(self):
        self.assertIn("## Title", self.sub)

    def test_has_summary(self):
        self.assertIn("## Summary", self.sub)

    def test_has_prerequisites(self):
        self.assertIn("## Prerequisites", self.sub)

    def test_has_use_case(self):
        self.assertIn("## Use Case", self.sub)

    def test_has_aws_services(self):
        self.assertIn("## AWS Services Used", self.sub)

    def test_has_well_architected(self):
        self.assertIn("## AWS Well-Architected", self.sub)

    def test_has_troubleshooting(self):
        self.assertIn("## Troubleshooting", self.sub)

    def test_lists_all_aws_services(self):
        services = [
            "HealthLake", "Bedrock", "Transcribe", "Lambda",
            "ECS Fargate", "S3", "DynamoDB", "Aurora",
            "Step Functions", "SQS", "AppSync", "Cognito",
            "KMS", "WAF", "VPC", "CloudWatch", "CloudTrail",
            "Budgets", "SNS",
        ]
        for svc in services:
            self.assertIn(svc, self.sub, f"Missing service in SUBMISSION: {svc}")

    def test_regions_match_prompt(self):
        self.assertIn("ca-central-1", self.sub)
        self.assertIn("us-east-1", self.sub)


# ===========================================================================
# 8. COMPETITION CRITERIA ALIGNMENT
# ===========================================================================
class TestCompetitionCriteria(unittest.TestCase):
    """Verify prompt meets all 4 winning criteria."""

    @classmethod
    def setUpClass(cls):
        cls.prompt = read_file("prompt.md")
        cls.sub = read_file("SUBMISSION.md")

    def test_clear_and_actionable_has_specific_values(self):
        # Must have specific parameter values, not vague instructions
        specifics = [
            "Python 3.11", "512 tokens", "20% overlap",
            "0.5 vCPU", "1GB", "256KB", "3-minute",
            "LOINC 8867-4", "LOINC 59408-5",
        ]
        for s in specifics:
            self.assertIn(s, self.prompt, f"Missing specific value: {s}")

    def test_production_ready_has_security(self):
        security = ["KMS", "CMK", "WAF", "Cognito", "VPC", "private subnet"]
        for s in security:
            self.assertIn(s, self.prompt, f"Missing security: {s}")

    def test_production_ready_has_monitoring(self):
        self.assertIn("CloudWatch", self.prompt)
        self.assertIn("CloudTrail", self.prompt)
        self.assertIn("alarm", self.prompt.lower())

    def test_production_ready_has_cost_controls(self):
        self.assertIn("Budget", self.prompt)
        self.assertIn("progressive degradation", self.prompt)

    def test_well_documented_has_troubleshooting(self):
        self.assertIn("TROUBLESHOOTING", self.prompt)
        problems = self.prompt.count("PROBLEM:")
        self.assertGreaterEqual(problems, 7)

    def test_well_documented_has_examples(self):
        # Has example language sets, example vocabulary, example prompts
        self.assertIn("Example language sets", self.prompt)
        self.assertIn("homa=fever", self.prompt)

    def test_best_practice_all_six_pillars(self):
        pillars = [
            "OPERATIONAL EXCELLENCE", "SECURITY", "RELIABILITY",
            "PERFORMANCE EFFICIENCY", "COST OPTIMIZATION", "SUSTAINABILITY",
        ]
        for p in pillars:
            self.assertIn(p, self.prompt)


if __name__ == "__main__":
    unittest.main()
