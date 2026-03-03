"""Whale audio classification pipeline.

Two-stage architecture:
  1. Feature extraction — mel spectrograms + acoustic descriptors via librosa.
  2. Species classification — XGBoost on extracted features (default) or
     optional CNN on mel-spectrogram images (requires torch).
"""
