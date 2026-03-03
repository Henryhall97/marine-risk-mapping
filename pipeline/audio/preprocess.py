"""Audio preprocessing for whale vocalisation classification.

Handles loading, resampling, segmentation into fixed-duration windows,
spectrogram computation (mel + PCEN), and acoustic feature extraction.
All parameters are drawn from pipeline.config to stay centralised.

Dependencies: librosa, soundfile, numpy
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    import pandas as pd

from pipeline.config import (
    AUDIO_FMAX,
    AUDIO_FMIN,
    AUDIO_HOP_LENGTH,
    AUDIO_N_FFT,
    AUDIO_N_MELS,
    AUDIO_N_MFCC,
    AUDIO_SAMPLE_RATE,
    AUDIO_SEGMENT_DURATION,
    AUDIO_SEGMENT_HOP,
    WHALE_FREQ_BANDS,
)

log = logging.getLogger(__name__)


# ── Loading & resampling ────────────────────────────────────


def load_audio(
    path: str | Path,
    target_sr: int = AUDIO_SAMPLE_RATE,
    mono: bool = True,
    max_duration_sec: float | None = None,
) -> tuple[np.ndarray, int]:
    """Load an audio file and resample to *target_sr* Hz mono.

    Supports WAV, FLAC, OGG, MP3 (via soundfile / audioread).

    Parameters
    ----------
    max_duration_sec : float | None
        If set, only load this many seconds from the start of the file.
        Prevents loading entire 24-hour recordings into memory when
        only a fraction will be used.

    Returns
    -------
    waveform : np.ndarray, shape (n_samples,) for mono
    sr : int  — always equals *target_sr*
    """
    import librosa

    y, sr = librosa.load(
        str(path),
        sr=target_sr,
        mono=mono,
        duration=max_duration_sec,
    )
    log.info("Loaded %s  — %.1f s @ %d Hz", Path(path).name, len(y) / sr, sr)
    return y, sr


# ── Segmentation ────────────────────────────────────────────


def segment_audio(
    waveform: np.ndarray,
    sr: int,
    segment_duration: float = AUDIO_SEGMENT_DURATION,
    hop_duration: float = AUDIO_SEGMENT_HOP,
    min_length_frac: float = 0.5,
) -> list[np.ndarray]:
    """Slice waveform into overlapping fixed-duration windows.

    Parameters
    ----------
    waveform : 1-D array of samples
    sr : sample rate
    segment_duration : window length in seconds
    hop_duration : hop between window starts in seconds
    min_length_frac : discard trailing segment shorter than this fraction

    Returns
    -------
    List of 1-D arrays, each of length ``int(segment_duration * sr)``
    (zero-padded if the final accepted window is shorter).
    """
    seg_samples = int(segment_duration * sr)
    hop_samples = int(hop_duration * sr)
    min_samples = int(seg_samples * min_length_frac)
    total = len(waveform)

    segments: list[np.ndarray] = []
    start = 0
    while start < total:
        end = start + seg_samples
        chunk = waveform[start:end]
        if len(chunk) < min_samples:
            break
        # Zero-pad if shorter than full window
        if len(chunk) < seg_samples:
            chunk = np.pad(chunk, (0, seg_samples - len(chunk)))
        segments.append(chunk)
        start += hop_samples

    log.debug(
        "Segmented %.1f s → %d windows (%.1f s, hop %.1f s)",
        total / sr,
        len(segments),
        segment_duration,
        hop_duration,
    )
    return segments


# ── Spectrogram computation ─────────────────────────────────


def compute_mel_spectrogram(
    waveform: np.ndarray,
    sr: int = AUDIO_SAMPLE_RATE,
    n_mels: int = AUDIO_N_MELS,
    n_fft: int = AUDIO_N_FFT,
    hop_length: int = AUDIO_HOP_LENGTH,
    fmin: float = AUDIO_FMIN,
    fmax: float = AUDIO_FMAX,
    power_to_db: bool = True,
) -> np.ndarray:
    """Compute a log-mel spectrogram.

    Returns shape ``(n_mels, T)`` where ``T = ceil(n_samples / hop_length)``.
    """
    import librosa

    S = librosa.feature.melspectrogram(
        y=waveform,
        sr=sr,
        n_fft=n_fft,
        hop_length=hop_length,
        n_mels=n_mels,
        fmin=fmin,
        fmax=fmax,
    )
    if power_to_db:
        S = librosa.power_to_db(S, ref=np.max)
    return S


def compute_pcen(
    waveform: np.ndarray,
    sr: int = AUDIO_SAMPLE_RATE,
    n_mels: int = AUDIO_N_MELS,
    n_fft: int = AUDIO_N_FFT,
    hop_length: int = AUDIO_HOP_LENGTH,
    fmin: float = AUDIO_FMIN,
    fmax: float = AUDIO_FMAX,
) -> np.ndarray:
    """Compute a PCEN (Per-Channel Energy Normalisation) spectrogram.

    PCEN is preferred over log-mel for bioacoustics because it adapts to
    non-stationary background noise (e.g. ship engine hum, wave action).
    The Google humpback model uses PCEN internally.

    Returns shape ``(n_mels, T)``.
    """
    import librosa

    S = librosa.feature.melspectrogram(
        y=waveform,
        sr=sr,
        n_fft=n_fft,
        hop_length=hop_length,
        n_mels=n_mels,
        fmin=fmin,
        fmax=fmax,
        power=1,  # magnitude spectrogram for PCEN
    )
    return librosa.pcen(S * (2**31), sr=sr, hop_length=hop_length)


# ── Acoustic feature extraction ─────────────────────────────


def compute_acoustic_features(
    waveform: np.ndarray,
    sr: int = AUDIO_SAMPLE_RATE,
    n_mfcc: int = AUDIO_N_MFCC,
    n_fft: int = AUDIO_N_FFT,
    hop_length: int = AUDIO_HOP_LENGTH,
    fmin: float = AUDIO_FMIN,
    fmax: float = AUDIO_FMAX,
) -> dict[str, float]:
    """Extract a flat dictionary of acoustic descriptors for one window.

    Returns ~60 features suitable for XGBoost classification:
      - MFCCs (mean + std of each coefficient)
      - Spectral centroid, bandwidth, rolloff, flatness
      - Zero crossing rate
      - RMS energy
      - Dominant frequency
      - Spectral contrast (7 bands, mean)
      - Temporal envelope statistics (attack time, decay)
    """
    import librosa

    feats: dict[str, float] = {}

    # MFCCs
    mfcc = librosa.feature.mfcc(
        y=waveform,
        sr=sr,
        n_mfcc=n_mfcc,
        n_fft=n_fft,
        hop_length=hop_length,
        fmin=fmin,
        fmax=fmax,
    )
    for i in range(n_mfcc):
        feats[f"mfcc_{i}_mean"] = float(np.mean(mfcc[i]))
        feats[f"mfcc_{i}_std"] = float(np.std(mfcc[i]))

    # Spectral centroid
    sc = librosa.feature.spectral_centroid(
        y=waveform, sr=sr, n_fft=n_fft, hop_length=hop_length
    )
    feats["spectral_centroid_mean"] = float(np.mean(sc))
    feats["spectral_centroid_std"] = float(np.std(sc))

    # Spectral bandwidth
    sb = librosa.feature.spectral_bandwidth(
        y=waveform, sr=sr, n_fft=n_fft, hop_length=hop_length
    )
    feats["spectral_bandwidth_mean"] = float(np.mean(sb))
    feats["spectral_bandwidth_std"] = float(np.std(sb))

    # Spectral rolloff (85th percentile)
    sr_roll = librosa.feature.spectral_rolloff(
        y=waveform, sr=sr, n_fft=n_fft, hop_length=hop_length, roll_percent=0.85
    )
    feats["spectral_rolloff_mean"] = float(np.mean(sr_roll))

    # Spectral flatness (tonal vs noise-like)
    sf = librosa.feature.spectral_flatness(
        y=waveform, n_fft=n_fft, hop_length=hop_length
    )
    feats["spectral_flatness_mean"] = float(np.mean(sf))
    feats["spectral_flatness_std"] = float(np.std(sf))

    # Spectral contrast (7 bands)
    contrast = librosa.feature.spectral_contrast(
        y=waveform, sr=sr, n_fft=n_fft, hop_length=hop_length, fmin=max(fmin, 20)
    )
    for i in range(contrast.shape[0]):
        feats[f"spectral_contrast_{i}_mean"] = float(np.mean(contrast[i]))

    # Zero crossing rate
    zcr = librosa.feature.zero_crossing_rate(y=waveform, hop_length=hop_length)
    feats["zcr_mean"] = float(np.mean(zcr))
    feats["zcr_std"] = float(np.std(zcr))

    # RMS energy
    rms = librosa.feature.rms(y=waveform, hop_length=hop_length)
    feats["rms_mean"] = float(np.mean(rms))
    feats["rms_std"] = float(np.std(rms))
    feats["rms_max"] = float(np.max(rms))

    # Dominant frequency via FFT
    fft_mag = np.abs(np.fft.rfft(waveform))
    freqs = np.fft.rfftfreq(len(waveform), d=1.0 / sr)
    feats["dominant_freq_hz"] = float(freqs[np.argmax(fft_mag)])

    # Temporal envelope stats
    envelope = np.abs(waveform)
    feats["envelope_mean"] = float(np.mean(envelope))
    feats["envelope_std"] = float(np.std(envelope))
    feats["envelope_skew"] = float(
        np.mean(((envelope - envelope.mean()) / (envelope.std() + 1e-8)) ** 3)
    )
    feats["envelope_kurtosis"] = float(
        np.mean(((envelope - envelope.mean()) / (envelope.std() + 1e-8)) ** 4) - 3.0
    )

    return feats


# ── Audio data augmentation ─────────────────────────────────


def augment_waveform(
    waveform: np.ndarray,
    sr: int,
    strategy: str = "all",
    rng: np.random.Generator | None = None,
) -> np.ndarray:
    """Apply a single random augmentation to a waveform segment.

    Parameters
    ----------
    waveform : 1-D float array
    sr : sample rate
    strategy : which augmentation to apply.
        ``"time_stretch"``, ``"pitch_shift"``, ``"add_noise"``,
        ``"time_shift"``, or ``"all"`` (picks one at random).
    rng : numpy random generator (for reproducibility)

    Returns
    -------
    Augmented waveform (same length as input).
    """
    if rng is None:
        rng = np.random.default_rng()

    if strategy == "all":
        strategy = rng.choice(
            ["time_stretch", "pitch_shift", "add_noise", "time_shift"]
        )

    original_len = len(waveform)

    if strategy == "time_stretch":
        import librosa

        from pipeline.config import AUDIO_AUG_TIME_STRETCH_RANGE

        lo, hi = AUDIO_AUG_TIME_STRETCH_RANGE
        rate = rng.uniform(lo, hi)
        y_aug = librosa.effects.time_stretch(waveform, rate=rate)
        # Trim or pad back to original length
        if len(y_aug) > original_len:
            y_aug = y_aug[:original_len]
        elif len(y_aug) < original_len:
            y_aug = np.pad(y_aug, (0, original_len - len(y_aug)))
        return y_aug

    elif strategy == "pitch_shift":
        import librosa

        from pipeline.config import AUDIO_AUG_PITCH_SHIFT_RANGE

        lo, hi = AUDIO_AUG_PITCH_SHIFT_RANGE
        n_steps = rng.uniform(lo, hi)
        return librosa.effects.pitch_shift(
            waveform,
            sr=sr,
            n_steps=n_steps,
        )

    elif strategy == "add_noise":
        from pipeline.config import AUDIO_AUG_NOISE_SNR_RANGE

        lo, hi = AUDIO_AUG_NOISE_SNR_RANGE
        snr_db = rng.uniform(lo, hi)
        signal_power = np.mean(waveform**2) + 1e-10
        noise_power = signal_power / (10 ** (snr_db / 10))
        noise = rng.normal(0, np.sqrt(noise_power), size=original_len).astype(
            waveform.dtype
        )
        return waveform + noise

    elif strategy == "time_shift":
        from pipeline.config import AUDIO_AUG_TIME_SHIFT_FRACTION

        max_shift = int(original_len * AUDIO_AUG_TIME_SHIFT_FRACTION)
        shift = rng.integers(-max_shift, max_shift)
        return np.roll(waveform, shift)

    else:
        log.warning("Unknown augmentation strategy '%s' — returning original", strategy)
        return waveform


def augment_segments(
    segments: list[np.ndarray],
    sr: int,
    target_count: int,
    seed: int = 42,
) -> list[tuple[np.ndarray, bool]]:
    """Augment a list of waveform segments up to *target_count*.

    Returns a list of ``(waveform, is_augmented)`` tuples.
    Original segments come first (``is_augmented=False``), then
    augmented copies are appended until we reach *target_count*.

    If ``len(segments) >= target_count``, returns originals only.
    """
    rng = np.random.default_rng(seed)
    result: list[tuple[np.ndarray, bool]] = [(s, False) for s in segments]

    n_needed = target_count - len(segments)
    if n_needed <= 0:
        return result

    # Cycle through originals, applying a random augmentation each time
    for i in range(n_needed):
        src = segments[i % len(segments)]
        aug = augment_waveform(src, sr, strategy="all", rng=rng)
        result.append((aug, True))

    log.debug(
        "Augmented %d originals → %d total (%d synthetic)",
        len(segments),
        len(result),
        n_needed,
    )
    return result


# ── Bandpass filtering ──────────────────────────────────────


def bandpass_filter(
    waveform: np.ndarray,
    sr: int,
    low_hz: float,
    high_hz: float,
    order: int = 5,
) -> np.ndarray:
    """Apply a Butterworth bandpass filter.

    Useful for isolating species-specific frequency bands before
    feature extraction (e.g. 15-30 Hz for fin whale 20 Hz pulses).
    """
    from scipy.signal import butter, sosfilt

    nyquist = sr / 2.0
    low = max(low_hz / nyquist, 0.001)
    high = min(high_hz / nyquist, 0.999)
    sos = butter(order, [low, high], btype="band", output="sos")
    return sosfilt(sos, waveform).astype(np.float32)


def bandpass_for_species(
    waveform: np.ndarray,
    sr: int,
    species: str,
) -> np.ndarray:
    """Apply species-specific bandpass from WHALE_FREQ_BANDS config."""
    if species not in WHALE_FREQ_BANDS:
        log.warning(
            "No frequency band for species '%s' -- returning unfiltered",
            species,
        )
        return waveform
    low, high = WHALE_FREQ_BANDS[species]
    return bandpass_filter(waveform, sr, low, high)


# ── End-to-end preprocessing ────────────────────────────────


def preprocess_file(
    audio_path: str | Path,
    target_sr: int = AUDIO_SAMPLE_RATE,
    segment_duration: float = AUDIO_SEGMENT_DURATION,
    segment_hop: float = AUDIO_SEGMENT_HOP,
    species_filter: str | None = None,
    max_segments: int | None = None,
) -> list[dict]:
    """Full preprocessing pipeline for one audio file.

    Parameters
    ----------
    max_segments : int | None
        If set, stop after this many segments.  Avoids spending minutes
        on 24-hour files when only a fraction of segments will be kept.

    Returns a list of dicts, one per segment:
        {
            "segment_idx": int,
            "waveform": np.ndarray,         # raw segment
            "mel_spectrogram": np.ndarray,   # (n_mels, T)
            "pcen": np.ndarray,              # (n_mels, T)
            "features": dict[str, float],    # acoustic descriptors
            "start_sec": float,
            "end_sec": float,
        }
    """
    # If we have a segment cap, compute the max audio duration we actually
    # need so we don't load an entire 24-hour file into memory.
    max_duration_sec = None
    if max_segments:
        # We need enough audio for max_segments hops + one full segment
        max_duration_sec = max_segments * segment_hop + segment_duration

    y, sr = load_audio(
        audio_path, target_sr=target_sr, max_duration_sec=max_duration_sec
    )

    if species_filter:
        y = bandpass_for_species(y, sr, species_filter)

    segments = segment_audio(y, sr, segment_duration, segment_hop)
    results = []
    for idx, seg in enumerate(segments):
        if max_segments and idx >= max_segments:
            log.info(
                "  Early stop: %s — processed %d / %d segments (cap)",
                Path(audio_path).name,
                max_segments,
                len(segments),
            )
            break
        start_sec = idx * segment_hop
        end_sec = start_sec + segment_duration
        results.append(
            {
                "segment_idx": idx,
                "waveform": seg,
                "mel_spectrogram": compute_mel_spectrogram(seg, sr),
                "pcen": compute_pcen(seg, sr),
                "features": compute_acoustic_features(seg, sr),
                "start_sec": start_sec,
                "end_sec": end_sec,
            }
        )

    log.info(
        "Preprocessed %s → %d segments, %d features each",
        Path(audio_path).name,
        len(results),
        len(results[0]["features"]) if results else 0,
    )
    return results


def extract_feature_matrix(
    audio_paths: list[str | Path],
    labels: list[str] | None = None,
    species_filter: str | None = None,
    max_segments_per_label: int | None = None,
) -> pd.DataFrame:
    """Extract acoustic features from multiple files into a DataFrame.

    Each row is one segment. Columns: all acoustic features + metadata.
    If *labels* is provided, a ``species`` column is added.

    Parameters
    ----------
    max_segments_per_label : int | None
        If set, stop extracting segments for a given label once this many
        have been collected.  Avoids wasting minutes on 24-hour files when
        only 2 000 segments per species will be kept.
    """
    import pandas as pd

    rows: list[dict] = []
    # Track how many segments have been collected per label so we can
    # skip files once the cap is reached.
    label_counts: dict[str, int] = {}

    for i, path in enumerate(audio_paths):
        lbl = labels[i] if labels is not None else None

        # Early exit: skip this file if the label already hit the cap
        if (
            max_segments_per_label
            and lbl is not None
            and label_counts.get(lbl, 0) >= max_segments_per_label
        ):
            continue

        # Compute how many segments we can still accept for this label
        remaining = None
        if max_segments_per_label and lbl is not None:
            remaining = max_segments_per_label - label_counts.get(lbl, 0)
            if remaining <= 0:
                continue  # redundant guard — outer check should catch this

        try:
            segments = preprocess_file(
                path,
                species_filter=species_filter,
                max_segments=remaining,
            )
        except Exception:
            log.warning("Failed to preprocess %s — skipping", path, exc_info=True)
            continue

        for seg in segments:
            # Per-segment cap check (within a single long file)
            if (
                max_segments_per_label
                and lbl is not None
                and label_counts.get(lbl, 0) >= max_segments_per_label
            ):
                skipped = len(segments) - seg["segment_idx"]
                log.info(
                    "  Cap reached for %s (%d segments) — skipping remaining %d in %s",
                    lbl,
                    max_segments_per_label,
                    skipped,
                    Path(path).name,
                )
                break

            row = {
                "file": str(Path(path).name),
                "segment_idx": seg["segment_idx"],
                "start_sec": seg["start_sec"],
                "end_sec": seg["end_sec"],
                **seg["features"],
            }
            if lbl is not None:
                row["species"] = lbl
            rows.append(row)

            if lbl is not None:
                label_counts[lbl] = label_counts.get(lbl, 0) + 1

    df = pd.DataFrame(rows)
    log.info(
        "Feature matrix: %d segments from %d files, %d feature columns",
        len(df),
        len(audio_paths),
        len(df.columns) - 4 - (1 if labels else 0),
    )
    return df
