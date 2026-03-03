"""Whale photo classification pipeline.

Single-stage architecture:
  EfficientNet-B4 fine-tuned from ImageNet weights on mixed body views
  (fluke, dorsal fin, flank) for 8-class whale species classification.
"""
