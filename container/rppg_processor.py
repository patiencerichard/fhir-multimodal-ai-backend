# rPPG Processor — CHROM algorithm with skin-tone adaptive preprocessing
# Generated from prompt.md Layer 2, Path B

import json
import os
import sys
import boto3
import cv2
import numpy as np
from scipy.signal import butter, filtfilt, find_peaks

s3 = boto3.client("s3")
events = boto3.client("events")

EVENT_BUS = os.environ.get("EVENT_BUS", "default")
BUCKET = os.environ["VIDEO_BUCKET"]
KEY = os.environ["VIDEO_KEY"]
PATIENT_ID = os.environ["PATIENT_ID"]
ENCOUNTER_ID = os.environ["ENCOUNTER_ID"]
SKIN_TONE = os.environ.get("SKIN_TONE", "standard")  # standard | dark


def main():
    # Download video from S3
    local_path = "/tmp/video.mp4"
    s3.download_file(BUCKET, KEY, local_path)

    # Extract face ROI frames
    rgb_signals = extract_face_rgb(local_path)

    if rgb_signals is None:
        emit_result(None, None, "low", "low", "failed")
        sys.exit(0)

    # Apply skin-tone adaptive preprocessing
    if SKIN_TONE == "dark":
        rgb_signals = dark_skin_preprocess(rgb_signals)

    # CHROM algorithm
    hr, hr_confidence = estimate_heart_rate(rgb_signals)
    spo2, spo2_confidence = estimate_spo2(rgb_signals)

    # Cap confidence for dark skin tones
    if SKIN_TONE == "dark":
        hr_confidence = min(hr_confidence, "moderate")
        spo2_confidence = min(spo2_confidence, "moderate")

    skin_flag = "reduced-confidence" if SKIN_TONE == "dark" else "standard"
    emit_result(hr, spo2, hr_confidence, spo2_confidence, skin_flag)


def extract_face_rgb(video_path):
    """Extract mean RGB from face ROI across all frames."""
    cap = cv2.VideoCapture(video_path)
    face_cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    )

    rgb_signals = []
    frame_count = 0

    while cap.isOpened() and frame_count < 450:  # 15s * 30fps
        ret, frame = cap.read()
        if not ret:
            break

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, 1.1, 5, minSize=(100, 100))

        if len(faces) > 0:
            x, y, w, h = faces[0]
            # Use forehead region (top 30% of face) for better signal
            roi = frame[y:y + int(h * 0.3), x:x + w]
            mean_rgb = roi.mean(axis=(0, 1))
            rgb_signals.append(mean_rgb)

        frame_count += 1

    cap.release()

    if len(rgb_signals) < 100:
        return None

    return np.array(rgb_signals)


def dark_skin_preprocess(rgb_signals):
    """Enhanced preprocessing for Fitzpatrick V-VI skin tones."""
    # Emphasize green channel (strongest PPG signal in darker skin)
    rgb_signals[:, 1] *= 1.5
    # Apply stronger bandpass to reduce noise
    for i in range(3):
        rgb_signals[:, i] = bandpass_filter(rgb_signals[:, i], 0.7, 3.5, 30)
    return rgb_signals


def estimate_heart_rate(rgb_signals, fps=30):
    """CHROM algorithm for heart rate estimation."""
    # Normalize channels
    r = rgb_signals[:, 2] / rgb_signals[:, 2].mean()
    g = rgb_signals[:, 1] / rgb_signals[:, 1].mean()
    b = rgb_signals[:, 0] / rgb_signals[:, 0].mean()

    # CHROM: Xs = 3R - 2G, Ys = 1.5R + G - 1.5B
    xs = 3 * r - 2 * g
    ys = 1.5 * r + g - 1.5 * b

    # Combine with alpha
    alpha = np.std(xs) / (np.std(ys) + 1e-10)
    pulse_signal = xs - alpha * ys

    # Bandpass filter (0.7-3.5 Hz = 42-210 bpm)
    filtered = bandpass_filter(pulse_signal, 0.7, 3.5, fps)

    # Find dominant frequency via FFT
    fft = np.abs(np.fft.rfft(filtered))
    freqs = np.fft.rfftfreq(len(filtered), 1.0 / fps)

    # Mask to valid HR range
    valid = (freqs >= 0.7) & (freqs <= 3.5)
    fft_valid = fft[valid]
    freqs_valid = freqs[valid]

    if len(fft_valid) == 0:
        return None, "low"

    peak_freq = freqs_valid[np.argmax(fft_valid)]
    hr = peak_freq * 60

    # Confidence based on signal-to-noise ratio
    snr = np.max(fft_valid) / (np.mean(fft_valid) + 1e-10)
    confidence = "high" if snr > 5 else "moderate" if snr > 2.5 else "low"

    return round(hr, 1), confidence


def estimate_spo2(rgb_signals):
    """Estimate SpO2 proxy from R/IR ratio approximation."""
    # Use red and blue channels as proxy for R/IR
    r_ac = np.std(rgb_signals[:, 2])
    r_dc = np.mean(rgb_signals[:, 2])
    b_ac = np.std(rgb_signals[:, 0])
    b_dc = np.mean(rgb_signals[:, 0])

    if r_dc == 0 or b_dc == 0:
        return None, "low"

    ratio = (r_ac / r_dc) / (b_ac / b_dc + 1e-10)

    # Empirical calibration (approximate — NOT medical grade)
    spo2 = 110 - 25 * ratio
    spo2 = max(70, min(100, spo2))

    # SpO2 from camera is inherently low confidence
    confidence = "moderate" if 0.3 < ratio < 1.5 else "low"

    return round(spo2, 1), confidence


def bandpass_filter(signal, low, high, fs, order=3):
    nyq = fs / 2
    b, a = butter(order, [low / nyq, high / nyq], btype="band")
    return filtfilt(b, a, signal)


def emit_result(hr, spo2, hr_conf, spo2_conf, skin_flag):
    """Send result to EventBridge for downstream processing."""
    events.put_events(Entries=[{
        "Source": "rppg-processor",
        "DetailType": "rPPG Result",
        "EventBusName": EVENT_BUS,
        "Detail": json.dumps({
            "patient_id": PATIENT_ID,
            "encounter_id": ENCOUNTER_ID,
            "heart_rate": hr,
            "spo2": spo2,
            "hr_confidence": hr_conf,
            "spo2_confidence": spo2_conf,
            "skin_tone_flag": skin_flag,
        }),
    }])


if __name__ == "__main__":
    main()
