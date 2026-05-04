# Cough Feature Extractor — MFCC extraction (13 coefficients)
# Generated from prompt.md Layer 2, Path C

import json
import io
import boto3
import numpy as np
from scipy.io import wavfile
from scipy.fftpack import dct

s3 = boto3.client("s3")

N_MFCC = 13
N_FILTERS = 26
FRAME_SIZE = 0.025  # 25ms
FRAME_STRIDE = 0.01  # 10ms


def handler(event, context):
    """Extract MFCC features from a single cough .wav sample."""
    bucket = event["bucket"]
    key = event["key"]

    obj = s3.get_object(Bucket=bucket, Key=key)
    sample_rate, signal = wavfile.read(io.BytesIO(obj["Body"].read()))

    if signal.ndim > 1:
        signal = signal[:, 0]
    signal = signal.astype(float)

    mfccs = extract_mfcc(signal, sample_rate)

    summary = {
        "mean": mfccs.mean(axis=0).tolist(),
        "std": mfccs.std(axis=0).tolist(),
        "min": mfccs.min(axis=0).tolist(),
        "max": mfccs.max(axis=0).tolist(),
    }

    return {"statusCode": 200, "mfcc_summary": summary, "source_key": key}


def extract_mfcc(signal, sample_rate):
    """Compute MFCCs from raw audio signal."""
    # Pre-emphasis
    emphasized = np.append(signal[0], signal[1:] - 0.97 * signal[:-1])

    # Framing
    frame_len = int(round(FRAME_SIZE * sample_rate))
    frame_step = int(round(FRAME_STRIDE * sample_rate))
    num_frames = max(1, int(np.ceil((len(emphasized) - frame_len) / frame_step)))

    pad_len = num_frames * frame_step + frame_len
    padded = np.append(emphasized, np.zeros(pad_len - len(emphasized)))

    indices = np.tile(np.arange(frame_len), (num_frames, 1)) + \
              np.tile(np.arange(0, num_frames * frame_step, frame_step), (frame_len, 1)).T
    frames = padded[indices.astype(int)]

    # Windowing + FFT
    frames *= np.hamming(frame_len)
    mag_frames = np.absolute(np.fft.rfft(frames, n=512))
    pow_frames = (1.0 / 512) * (mag_frames ** 2)

    # Mel filterbank
    low_freq_mel = 0
    high_freq_mel = 2595 * np.log10(1 + (sample_rate / 2) / 700)
    mel_points = np.linspace(low_freq_mel, high_freq_mel, N_FILTERS + 2)
    hz_points = 700 * (10 ** (mel_points / 2595) - 1)
    bins = np.floor((512 + 1) * hz_points / sample_rate).astype(int)

    fbank = np.zeros((N_FILTERS, 257))
    for m in range(1, N_FILTERS + 1):
        f_left, f_center, f_right = bins[m - 1], bins[m], bins[m + 1]
        for k in range(f_left, f_center):
            fbank[m - 1, k] = (k - f_left) / (f_center - f_left)
        for k in range(f_center, f_right):
            fbank[m - 1, k] = (f_right - k) / (f_right - f_center)

    filter_banks = np.dot(pow_frames, fbank.T)
    filter_banks = np.where(filter_banks == 0, np.finfo(float).eps, filter_banks)
    filter_banks = 20 * np.log10(filter_banks)

    # DCT to get MFCCs
    mfccs = dct(filter_banks, type=2, axis=1, norm="ortho")[:, :N_MFCC]
    return mfccs
