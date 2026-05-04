"""Load test — 50 concurrent CHW sessions with mixed modalities."""
from locust import HttpUser, task, between
import random
import json

LANGUAGES = ["sw-TZ", "sw-KE", "so-SO", "en-ZA", "fr-FR"]


class CHWUser(HttpUser):
    wait_time = between(5, 15)

    @task(60)
    def voice_triage(self):
        """Voice-only encounter (60% of traffic)."""
        self.client.post("/intake", json={
            "type": "voice",
            "language": random.choice(LANGUAGES),
            "audio_key": f"test/voice-{random.randint(1,1000)}.mp4",
            "patient_id": f"patient-{random.randint(1,200)}",
        })

    @task(25)
    def multimodal_triage(self):
        """Full multimodal: voice + rPPG + cough (25%)."""
        self.client.post("/intake", json={
            "type": "multimodal",
            "language": random.choice(LANGUAGES),
            "audio_key": f"test/voice-{random.randint(1,1000)}.mp4",
            "video_key": f"test/video-{random.randint(1,500)}.mp4",
            "cough_keys": [f"test/cough-{i}.wav" for i in range(5)],
            "patient_id": f"patient-{random.randint(1,200)}",
        })

    @task(10)
    def offline_sync(self):
        """Offline encounter sync (10%)."""
        self.client.post("/sync", json={
            "encounters": [{"id": f"offline-{random.randint(1,1000)}",
                           "sync_status": "PENDING"}],
        })

    @task(5)
    def text_triage(self):
        """Text-only quick check (5%)."""
        self.client.post("/intake", json={
            "type": "text",
            "language": "en-ZA",
            "text": "Patient has fever for 3 days and cough",
            "patient_id": f"patient-{random.randint(1,200)}",
        })
