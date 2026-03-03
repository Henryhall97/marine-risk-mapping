"""Tests for pipeline.audio — preprocessing and classification.

Covers the pure-compute functions that don't need audio files
on disk. Uses synthetic waveforms (sine tones) for determinism.
"""

import numpy as np

# ── segment_audio() ─────────────────────────────────────────


class TestSegmentAudio:
    """Slicing a waveform into fixed-length overlapping windows."""

    def test_exact_segments(self):
        from pipeline.audio.preprocess import segment_audio

        sr = 16_000
        # 4-second waveform with 4s window and 2s hop
        y = np.zeros(4 * sr, dtype=np.float32)
        segs = segment_audio(y, sr=sr, segment_duration=4.0, hop_duration=2.0)
        assert len(segs) >= 1
        assert segs[0].shape[0] == 4 * sr

    def test_short_audio_zero_padded(self):
        from pipeline.audio.preprocess import segment_audio

        sr = 16_000
        # 3-second waveform → should produce 1 zero-padded segment
        # (min_length_frac=0.5 → need at least 2s to keep)
        y = np.ones(3 * sr, dtype=np.float32)
        segs = segment_audio(y, sr=sr, segment_duration=4.0, hop_duration=2.0)
        assert len(segs) >= 1
        assert segs[0].shape[0] == 4 * sr

    def test_output_dtype_preserved(self):
        from pipeline.audio.preprocess import segment_audio

        sr = 16_000
        y = np.random.default_rng(0).random(8 * sr).astype(np.float32)
        segs = segment_audio(y, sr=sr, segment_duration=4.0, hop_duration=2.0)
        for seg in segs:
            assert seg.dtype == np.float32

    def test_empty_returns_empty(self):
        from pipeline.audio.preprocess import segment_audio

        sr = 16_000
        y = np.array([], dtype=np.float32)
        segs = segment_audio(y, sr=sr, segment_duration=4.0, hop_duration=2.0)
        assert len(segs) == 0

    def test_multiple_segments(self):
        from pipeline.audio.preprocess import segment_audio

        sr = 16_000
        # 10-second waveform, 4s window, 2s hop → starts at 0,2,4,6
        y = np.ones(10 * sr, dtype=np.float32)
        segs = segment_audio(y, sr=sr, segment_duration=4.0, hop_duration=2.0)
        assert len(segs) >= 3


# ── compute_acoustic_features() ─────────────────────────────


class TestComputeAcousticFeatures:
    """Acoustic feature extraction from a waveform segment."""

    def test_returns_dict(self, sine_waveform):
        from pipeline.audio.preprocess import compute_acoustic_features

        y, sr = sine_waveform
        y_padded = np.pad(y, (0, 3 * sr))
        feats = compute_acoustic_features(y_padded, sr=sr)
        assert isinstance(feats, dict)

    def test_feature_count(self, sine_waveform):
        from pipeline.audio.preprocess import compute_acoustic_features

        y, sr = sine_waveform
        y_padded = np.pad(y, (0, 3 * sr))
        feats = compute_acoustic_features(y_padded, sr=sr)
        # 20 MFCCs × 2 = 40 + spectral (8) + contrast (7) + ZCR (2)
        # + RMS (3) + dom_freq (1) + envelope (4) ≈ 65
        assert len(feats) >= 50, f"Only {len(feats)} features"

    def test_all_values_finite(self, sine_waveform):
        from pipeline.audio.preprocess import compute_acoustic_features

        y, sr = sine_waveform
        y_padded = np.pad(y, (0, 3 * sr))
        feats = compute_acoustic_features(y_padded, sr=sr)
        for k, v in feats.items():
            assert np.isfinite(v), f"{k} = {v} is not finite"

    def test_dominant_freq_near_440(self, sine_waveform):
        """A 440 Hz sine should have dominant frequency near 440."""
        from pipeline.audio.preprocess import compute_acoustic_features

        y, sr = sine_waveform
        y_padded = np.pad(y, (0, 3 * sr))
        feats = compute_acoustic_features(y_padded, sr=sr)
        assert 400 < feats["dominant_freq_hz"] < 480


# ── compute_mel_spectrogram() ───────────────────────────────


class TestMelSpectrogram:
    def test_shape(self, sine_waveform):
        from pipeline.audio.preprocess import compute_mel_spectrogram
        from pipeline.config import AUDIO_N_MELS

        y, sr = sine_waveform
        y_padded = np.pad(y, (0, 3 * sr))
        mel = compute_mel_spectrogram(y_padded, sr=sr)
        assert mel.ndim == 2
        assert mel.shape[0] == AUDIO_N_MELS

    def test_values_finite(self, sine_waveform):
        from pipeline.audio.preprocess import compute_mel_spectrogram

        y, sr = sine_waveform
        y_padded = np.pad(y, (0, 3 * sr))
        mel = compute_mel_spectrogram(y_padded, sr=sr)
        assert np.all(np.isfinite(mel))


# ── bandpass_filter() ───────────────────────────────────────


class TestBandpassFilter:
    def test_preserves_length(self, sine_waveform):
        from pipeline.audio.preprocess import bandpass_filter

        y, sr = sine_waveform
        filtered = bandpass_filter(y, sr=sr, low_hz=200, high_hz=600)
        assert filtered.shape == y.shape

    def test_passes_in_band_signal(self, sine_waveform):
        """440 Hz sine should mostly survive a 200–600 Hz filter."""
        from pipeline.audio.preprocess import bandpass_filter

        y, sr = sine_waveform
        filtered = bandpass_filter(y, sr=sr, low_hz=200, high_hz=600)
        power_ratio = np.sum(filtered**2) / np.sum(y**2)
        assert power_ratio > 0.5

    def test_rejects_out_of_band(self):
        """440 Hz sine should be attenuated by a 1000–2000 Hz filter."""
        from pipeline.audio.preprocess import bandpass_filter

        sr = 16_000
        t = np.linspace(0, 1.0, sr, endpoint=False)
        y = np.sin(2 * np.pi * 440 * t).astype(np.float32)
        filtered = bandpass_filter(y, sr=sr, low_hz=1000, high_hz=2000)
        power_ratio = np.sum(filtered**2) / np.sum(y**2)
        assert power_ratio < 0.1


# ── augment_waveform() ─────────────────────────────────────


class TestAugmentWaveform:
    def test_same_length(self, sine_waveform):
        from pipeline.audio.preprocess import augment_waveform

        y, sr = sine_waveform
        rng = np.random.default_rng(42)
        augmented = augment_waveform(y, sr=sr, rng=rng)
        assert augmented.shape == y.shape

    def test_deterministic_with_rng(self, sine_waveform):
        from pipeline.audio.preprocess import augment_waveform

        y, sr = sine_waveform
        rng1 = np.random.default_rng(42)
        a1 = augment_waveform(y.copy(), sr=sr, rng=rng1)
        rng2 = np.random.default_rng(42)
        a2 = augment_waveform(y.copy(), sr=sr, rng=rng2)
        assert np.allclose(a1, a2)

    def test_add_noise_strategy(self, sine_waveform):
        from pipeline.audio.preprocess import augment_waveform

        y, sr = sine_waveform
        rng = np.random.default_rng(0)
        aug = augment_waveform(y, sr=sr, strategy="add_noise", rng=rng)
        assert not np.allclose(aug, y)
        assert aug.shape == y.shape


# ── augment_segments() ─────────────────────────────────────


class TestAugmentSegments:
    def test_augments_small_class(self):
        from pipeline.audio.preprocess import augment_segments

        sr = 16_000
        seg_len = 4 * sr
        segments = [
            np.random.default_rng(i).random(seg_len).astype(np.float32)
            for i in range(3)
        ]
        result = augment_segments(segments, sr=sr, target_count=10)
        assert len(result) == 10
        # First 3 are originals
        for _, is_aug in result[:3]:
            assert is_aug is False
        # Rest are augmented
        for _, is_aug in result[3:]:
            assert is_aug is True

    def test_no_augmentation_needed(self):
        from pipeline.audio.preprocess import augment_segments

        sr = 16_000
        seg_len = 4 * sr
        segments = [
            np.random.default_rng(i).random(seg_len).astype(np.float32)
            for i in range(20)
        ]
        result = augment_segments(segments, sr=sr, target_count=10)
        # Already have enough — return originals only
        assert len(result) == 20
        for _, is_aug in result:
            assert is_aug is False
