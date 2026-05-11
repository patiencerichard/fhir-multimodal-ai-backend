"""Unit tests for fhir-multimodal-ai-backend Lambda functions.

Run with:
    .venv/bin/pytest tests/test_lambdas.py -v
"""
import io
import json
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Stub AWS SDK — not installed in venv, not needed for unit tests
# ---------------------------------------------------------------------------
sys.modules.setdefault("boto3", MagicMock())

# Add lambda/ to path
LAMBDA_DIR = os.path.join(os.path.dirname(__file__), "..", "lambda")
if LAMBDA_DIR not in sys.path:
    sys.path.insert(0, LAMBDA_DIR)


# ===========================================================================
# channel_router
# ===========================================================================
class TestChannelRouter(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import channel_router
        cls.cr = channel_router

    def _record(self, key, size):
        return {"s3": {"bucket": {"name": "b"}, "object": {"key": key, "size": size}}}

    def test_detect_cough(self):
        self.assertEqual(self.cr.detect_channel("cough/a.wav", 100), "cough")

    def test_detect_video(self):
        self.assertEqual(self.cr.detect_channel("v.mp4", 10_000_000), "video")

    def test_detect_voice(self):
        self.assertEqual(self.cr.detect_channel("v.wav", 500_000), "voice")

    def test_detect_text_fallback(self):
        self.assertEqual(self.cr.detect_channel("notes.txt", 100), "text")

    def test_validate_audio_ok(self):
        self.assertTrue(self.cr.validate_audio(5_000_000))

    def test_validate_audio_too_large(self):
        self.assertFalse(self.cr.validate_audio(11_000_000))

    def test_validate_video_ok(self):
        self.assertTrue(self.cr.validate_video(49_000_000))

    def test_validate_video_too_large(self):
        self.assertFalse(self.cr.validate_video(51_000_000))

    def test_handler_routes_voice(self):
        self.cr.sqs = MagicMock()
        self.cr.sqs.get_queue_url.return_value = {"QueueUrl": "http://q/voice"}
        resp = self.cr.handler({"Records": [self._record("v.wav", 500_000)]}, {})
        self.assertEqual(resp["statusCode"], 200)
        self.cr.sqs.send_message.assert_called_once()

    def test_handler_rejects_oversized_audio(self):
        self.cr.sqs = MagicMock()
        resp = self.cr.handler({"Records": [self._record("v.wav", 20_000_000)]}, {})
        self.assertEqual(resp["statusCode"], 400)

    def test_handler_rejects_oversized_video(self):
        self.cr.sqs = MagicMock()
        resp = self.cr.handler({"Records": [self._record("v.mp4", 60_000_000)]}, {})
        self.assertEqual(resp["statusCode"], 400)

    def test_handler_counts_routed_records(self):
        self.cr.sqs = MagicMock()
        self.cr.sqs.get_queue_url.return_value = {"QueueUrl": "http://q/cough"}
        records = [self._record("cough/a.wav", 100), self._record("cough/b.wav", 200)]
        resp = self.cr.handler({"Records": records}, {})
        self.assertEqual(json.loads(resp["body"])["routed"], 2)


# ===========================================================================
# cough_feature_extractor  (uses real numpy + scipy)
# ===========================================================================
class TestCoughFeatureExtractor(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import cough_feature_extractor
        cls.cfe = cough_feature_extractor

    def _mock_s3_wav(self, signal, sr=16000):
        import numpy as np
        from scipy.io import wavfile
        buf = io.BytesIO()
        wavfile.write(buf, sr, signal.astype(np.int16))
        buf.seek(0)
        self.cfe.s3 = MagicMock()
        self.cfe.s3.get_object.return_value = {"Body": MagicMock(read=buf.read)}

    def test_handler_returns_mfcc_summary(self):
        import numpy as np
        signal = (np.random.randn(16000) * 1000).astype(np.int16)
        self._mock_s3_wav(signal)
        result = self.cfe.handler({"bucket": "b", "key": "cough/x.wav"}, {})
        self.assertEqual(result["statusCode"], 200)
        for stat in ("mean", "std", "min", "max"):
            self.assertIn(stat, result["mfcc_summary"])
            self.assertEqual(len(result["mfcc_summary"][stat]), 13)

    def test_handler_stereo_to_mono(self):
        import numpy as np
        signal = (np.random.randn(16000, 2) * 1000).astype(np.int16)
        self._mock_s3_wav(signal)
        result = self.cfe.handler({"bucket": "b", "key": "cough/stereo.wav"}, {})
        self.assertEqual(result["statusCode"], 200)

    def test_extract_mfcc_shape(self):
        import numpy as np
        signal = np.random.randn(16000)
        mfccs = self.cfe.extract_mfcc(signal, 16000)
        self.assertEqual(mfccs.shape[1], 13)
        self.assertGreater(mfccs.shape[0], 0)

    def test_source_key_echoed(self):
        import numpy as np
        signal = (np.random.randn(8000) * 1000).astype(np.int16)
        self._mock_s3_wav(signal)
        result = self.cfe.handler({"bucket": "b", "key": "cough/y.wav"}, {})
        self.assertEqual(result["source_key"], "cough/y.wav")


# ===========================================================================
# transcription_orchestrator
# ===========================================================================
class TestTranscriptionOrchestrator(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("SESSION_TABLE", "sessions")
        os.environ.setdefault("VOCAB_BUCKET", "vocab")
        os.environ.setdefault("SUPPORTED_LANGUAGES", '["sw-TZ"]')
        import transcription_orchestrator
        cls.to = transcription_orchestrator

    def _record(self, bucket, key):
        return {"body": json.dumps({"bucket": bucket, "key": key})}

    def _ctx(self):
        ctx = MagicMock()
        ctx.get_remaining_time_in_millis.return_value = 30000
        return ctx

    def test_handler_starts_job(self):
        self.to.transcribe = MagicMock()
        self.to.table = MagicMock()
        resp = self.to.handler({"Records": [self._record("b", "audio/v.wav")]}, self._ctx())
        self.assertEqual(resp["statusCode"], 200)
        self.to.transcribe.start_transcription_job.assert_called_once()

    def test_single_language_uses_language_code(self):
        import importlib
        os.environ["SUPPORTED_LANGUAGES"] = '["sw-TZ"]'
        import transcription_orchestrator as to1
        importlib.reload(to1)
        to1.transcribe = MagicMock()
        to1.table = MagicMock()
        to1.handler({"Records": [self._record("b", "audio/v.wav")]}, self._ctx())
        kw = to1.transcribe.start_transcription_job.call_args[1]
        self.assertEqual(kw["LanguageCode"], "sw-TZ")
        self.assertNotIn("IdentifyLanguage", kw)

    def test_multi_language_uses_identification(self):
        import importlib
        os.environ["SUPPORTED_LANGUAGES"] = '["sw-TZ","sw-KE","en-ZA"]'
        import transcription_orchestrator as to2
        importlib.reload(to2)
        to2.transcribe = MagicMock()
        to2.table = MagicMock()
        to2.handler({"Records": [self._record("b", "audio/v.wav")]}, self._ctx())
        kw = to2.transcribe.start_transcription_job.call_args[1]
        self.assertTrue(kw.get("IdentifyLanguage"))
        os.environ["SUPPORTED_LANGUAGES"] = '["sw-TZ"]'

    def test_normalize_medical_terms(self):
        payload = [{"original": "homa", "english": "fever", "snomed_code": "386661006"}]
        body = MagicMock()
        body.read.return_value = json.dumps({"content": [{"text": json.dumps(payload)}]}).encode()
        self.to.bedrock = MagicMock()
        self.to.bedrock.invoke_model.return_value = {"body": body}
        result = self.to.normalize_medical_terms("mgonjwa ana homa", "sw-TZ")
        self.assertEqual(result[0]["english"], "fever")


# ===========================================================================
# rppg_result_handler
# ===========================================================================
class TestRppgResultHandler(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("HEALTHLAKE_DATASTORE_ID", "ds-123")
        import rppg_result_handler
        cls.rh = rppg_result_handler

    def _event(self, hr=72, spo2=98):
        return {"detail": {
            "patient_id": "p-001", "encounter_id": "e-001",
            "heart_rate": hr, "spo2": spo2,
            "hr_confidence": "HIGH", "spo2_confidence": "MEDIUM",
            "skin_tone_flag": "ITA3",
        }}

    def test_handler_writes_two_observations(self):
        self.rh.healthlake = MagicMock()
        resp = self.rh.handler(self._event(), {})
        self.assertEqual(resp["statusCode"], 200)
        self.assertEqual(resp["observations_written"], 2)
        self.assertEqual(self.rh.healthlake.create_resource.call_count, 2)

    def test_observation_structure(self):
        obs = self.rh.build_observation("p", "e", "8867-4", "Heart rate", 72, "bpm", "HIGH", "ITA3")
        self.assertEqual(obs["resourceType"], "Observation")
        self.assertEqual(obs["status"], "preliminary")
        self.assertEqual(obs["valueQuantity"]["value"], 72)
        self.assertEqual(obs["code"]["coding"][0]["code"], "8867-4")

    def test_observation_rppg_disclaimer(self):
        obs = self.rh.build_observation("p", "e", "8867-4", "HR", 70, "bpm", "LOW", "ITA1")
        self.assertIn("rPPG", obs["note"][0]["text"])
        self.assertIn("NOT a medical device", obs["note"][0]["text"])

    def test_observation_extensions(self):
        obs = self.rh.build_observation("p", "e", "59408-5", "SpO2", 97, "%", "MEDIUM", "ITA5")
        urls = [e["url"] for e in obs["extension"]]
        self.assertIn("measurement-confidence", urls)
        self.assertIn("skin-tone-flag", urls)


# ===========================================================================
# fhir_sync
# ===========================================================================
class TestFhirSync(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("HEALTHLAKE_DATASTORE_ID", "ds-123")
        import fhir_sync
        cls.fs = fhir_sync

    def _record(self, event_name, sync_status, rtype="Encounter"):
        body = json.dumps({"resourceType": rtype, "id": "r-001"})
        return {
            "eventName": event_name,
            "dynamodb": {"NewImage": {
                "sync_status": {"S": sync_status},
                "resource_type": {"S": rtype},
                "fhir_resource": {"S": body},
            }},
        }

    def test_syncs_pending_insert(self):
        self.fs.healthlake = MagicMock()
        resp = self.fs.handler({"Records": [self._record("INSERT", "PENDING")]}, {})
        self.assertEqual(resp["resources_synced"], 1)
        self.fs.healthlake.create_resource.assert_called_once()

    def test_skips_non_pending(self):
        self.fs.healthlake = MagicMock()
        resp = self.fs.handler({"Records": [self._record("INSERT", "SYNCED")]}, {})
        self.assertEqual(resp["resources_synced"], 0)
        self.fs.healthlake.create_resource.assert_not_called()

    def test_skips_delete_events(self):
        self.fs.healthlake = MagicMock()
        resp = self.fs.handler({"Records": [self._record("REMOVE", "PENDING")]}, {})
        self.assertEqual(resp["resources_synced"], 0)

    def test_tags_offline_origin(self):
        self.fs.healthlake = MagicMock()
        self.fs.handler({"Records": [self._record("INSERT", "PENDING")]}, {})
        body = json.loads(self.fs.healthlake.create_resource.call_args[1]["ResourceBody"])
        self.assertTrue(any(t["code"] == "offline-origin" for t in body["meta"]["tag"]))

    def test_counts_multiple_records(self):
        self.fs.healthlake = MagicMock()
        records = [
            self._record("INSERT", "PENDING"),
            self._record("MODIFY", "PENDING"),
            self._record("INSERT", "SYNCED"),
        ]
        resp = self.fs.handler({"Records": records}, {})
        self.assertEqual(resp["resources_synced"], 2)


# ===========================================================================
# budget_enforcer
# ===========================================================================
class TestBudgetEnforcer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("ECS_CLUSTER", "tibabu-cluster")
        os.environ.setdefault("RPPG_SERVICE", "rppg-service")
        os.environ.setdefault("COUGH_LAMBDA_NAME", "cough-extractor")
        os.environ.setdefault("ALERT_TOPIC_ARN", "arn:aws:sns:us-east-1:123:alerts")
        import budget_enforcer
        cls.be = budget_enforcer

    def _event(self, threshold):
        return {"Records": [{"Sns": {"Message": json.dumps({"ThresholdBreached": threshold})}}]}

    def setUp(self):
        self.be.ecs = MagicMock()
        self.be.lambda_client = MagicMock()
        self.be.sns = MagicMock()

    def test_80_disables_rppg(self):
        self.be.handler(self._event("80"), {})
        self.be.ecs.update_service.assert_called_once_with(
            cluster="tibabu-cluster", service="rppg-service", desiredCount=0
        )
        self.be.lambda_client.put_function_concurrency.assert_not_called()

    def test_90_disables_cough(self):
        self.be.handler(self._event("90"), {})
        self.be.lambda_client.put_function_concurrency.assert_called_once_with(
            FunctionName="cough-extractor", ReservedConcurrentExecutions=0
        )

    def test_100_notifies_haiku_routing(self):
        self.be.handler(self._event("100"), {})
        msg = self.be.sns.publish.call_args[1]["Message"]
        self.assertIn("Haiku", msg)

    def test_voice_never_disabled(self):
        for t in ("80", "90", "100"):
            self.be.handler(self._event(t), {})
        for call in self.be.ecs.update_service.call_args_list:
            self.assertNotIn("voice", str(call).lower())


# ===========================================================================
# clinical_reasoning
# ===========================================================================
class TestClinicalReasoning(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("HEALTHLAKE_DATASTORE_ID", "ds-123")
        os.environ.setdefault("KNOWLEDGE_BASE_ID", "kb-456")
        import clinical_reasoning
        cls.cr = clinical_reasoning

    def _triage(self, category="ROUTINE"):
        return {
            "triage_category": category, "differentials": [],
            "chw_actions": [], "physician_referral_reasons": [],
            "drug_interactions": [],
            "response_english": "Monitor.", "response_local_language": "Angalia.",
            "confidence": "MEDIUM",
        }

    def _mock_bedrock(self, payload):
        body = MagicMock()
        body.read.return_value = json.dumps({"content": [{"text": json.dumps(payload)}]}).encode()
        self.cr.bedrock = MagicMock()
        self.cr.bedrock.invoke_model.return_value = {"body": body}
        self.cr.bedrock_agent = MagicMock()
        self.cr.bedrock_agent.retrieve.return_value = {"retrievalResults": []}

    def _encounter(self, **kw):
        enc = {
            "patient_id": "p-001",
            "transcript_english": "fever and cough",
            "transcript_original": "homa na kikohozi",
            "source_language": "sw-TZ",
            "heart_rate": 88, "hr_confidence": "MEDIUM",
            "spo2": 97, "spo2_confidence": "MEDIUM",
            "cough_risk_score": 45, "risk_tier": "MODERATE",
            "age": 30, "sex": "M", "region": "Dar es Salaam",
        }
        enc.update(kw)
        return enc

    def test_handler_returns_triage(self):
        self._mock_bedrock(self._triage())
        self.cr.healthlake = MagicMock()
        resp = self.cr.handler({"encounter": self._encounter()}, {})
        self.assertEqual(resp["statusCode"], 200)
        self.assertIn("triage", resp)

    def test_handler_writes_fhir_encounter(self):
        self._mock_bedrock(self._triage())
        self.cr.healthlake = MagicMock()
        self.cr.handler({"encounter": self._encounter()}, {})
        self.cr.healthlake.create_resource.assert_called_once()
        self.assertEqual(
            self.cr.healthlake.create_resource.call_args[1]["ResourceType"], "Encounter"
        )

    def test_estimate_tokens_scales_with_size(self):
        self.assertGreater(
            self.cr.estimate_tokens({"a": "x" * 1000}),
            self.cr.estimate_tokens({"a": "x"}),
        )

    def test_prompt_has_safety_disclaimer(self):
        prompt = self.cr.build_prompt(self._encounter(), "")
        self.assertIn("ASSIST", prompt)
        self.assertIn("NOT replace", prompt)

    def test_prompt_has_spo2_threshold_rule(self):
        self.assertIn("SpO2 < 94%", self.cr.build_prompt(self._encounter(), ""))

    def test_retrieve_guidelines_truncates_to_1000(self):
        self.cr.bedrock_agent = MagicMock()
        self.cr.bedrock_agent.retrieve.return_value = {
            "retrievalResults": [{"content": {"text": "guideline"}}]
        }
        self.cr.retrieve_guidelines(self._encounter(transcript_english="x" * 2000))
        query = self.cr.bedrock_agent.retrieve.call_args[1]["retrievalQuery"]["text"]
        self.assertLessEqual(len(query), 1000)


if __name__ == "__main__":
    unittest.main()
