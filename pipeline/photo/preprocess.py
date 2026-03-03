"""Image preprocessing for whale photo species classification.

Handles resizing, normalisation, augmentation, and a PyTorch Dataset
class for training and inference.  All parameters are drawn from
pipeline.config to stay centralised.

Dependencies: torch, torchvision, Pillow (via torchvision)
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from collections.abc import Callable

    from PIL import Image as PILImage

from pipeline.config import (
    PHOTO_IMAGE_SIZE,
    PHOTO_IMAGENET_MEAN,
    PHOTO_IMAGENET_STD,
)

log = logging.getLogger(__name__)


# ── Transforms ──────────────────────────────────────────────


def get_train_transforms() -> Callable:
    """Return torchvision transforms for training augmentation.

    Applies: random resized crop, horizontal flip, rotation (±15°),
    colour jitter, then normalise to ImageNet statistics.
    """
    from torchvision import transforms

    return transforms.Compose(
        [
            transforms.RandomResizedCrop(
                PHOTO_IMAGE_SIZE,
                scale=(0.8, 1.0),
                ratio=(0.9, 1.1),
            ),
            transforms.RandomHorizontalFlip(p=0.5),
            transforms.RandomRotation(degrees=15),
            transforms.ColorJitter(
                brightness=0.2,
                contrast=0.2,
                saturation=0.2,
            ),
            transforms.ToTensor(),
            transforms.Normalize(
                mean=PHOTO_IMAGENET_MEAN,
                std=PHOTO_IMAGENET_STD,
            ),
        ]
    )


def get_val_transforms() -> Callable:
    """Return torchvision transforms for validation / inference.

    Applies: resize, centre crop, normalise.  No augmentation.
    """
    from torchvision import transforms

    return transforms.Compose(
        [
            transforms.Resize(PHOTO_IMAGE_SIZE + 32),
            transforms.CenterCrop(PHOTO_IMAGE_SIZE),
            transforms.ToTensor(),
            transforms.Normalize(
                mean=PHOTO_IMAGENET_MEAN,
                std=PHOTO_IMAGENET_STD,
            ),
        ]
    )


# ── Dataset ─────────────────────────────────────────────────


class WhalePhotoDataset:
    """PyTorch-compatible dataset for whale species photo classification.

    Parameters
    ----------
    image_paths : list[Path]
        Absolute paths to JPEG images.
    labels : list[int]
        Integer-encoded species labels (aligned with image_paths).
    transform : Callable | None
        torchvision transform pipeline.  Use ``get_train_transforms()``
        for training, ``get_val_transforms()`` for validation.
    """

    def __init__(
        self,
        image_paths: list[Path],
        labels: list[int],
        transform: Callable | None = None,
    ):
        self.image_paths = image_paths
        self.labels = labels
        self.transform = transform

    def __len__(self) -> int:
        return len(self.image_paths)

    def __getitem__(self, idx: int) -> tuple:
        import torch
        from PIL import Image

        path = self.image_paths[idx]
        label = self.labels[idx]

        try:
            img = Image.open(path).convert("RGB")
        except Exception:
            log.warning("Failed to load %s — returning black image", path)
            img = Image.new("RGB", (PHOTO_IMAGE_SIZE, PHOTO_IMAGE_SIZE))

        if self.transform:
            img = self.transform(img)
        else:
            # Fallback: just resize + tensor
            from torchvision import transforms

            img = transforms.Compose(
                [
                    transforms.Resize((PHOTO_IMAGE_SIZE, PHOTO_IMAGE_SIZE)),
                    transforms.ToTensor(),
                ]
            )(img)

        return img, torch.tensor(label, dtype=torch.long)


# ── Utility functions ───────────────────────────────────────


def load_and_preprocess(
    image_path: str | Path,
) -> PILImage.Image:
    """Load a single image for inference (no label needed).

    Returns a PIL Image in RGB mode, ready for transform application.
    """
    from PIL import Image

    img = Image.open(str(image_path)).convert("RGB")
    return img


def extract_exif_gps(image_path: str | Path) -> tuple[float, float] | None:
    """Extract GPS coordinates from image EXIF metadata.

    Returns (lat, lon) in decimal degrees, or None if no GPS data.
    """
    from PIL import Image
    from PIL.ExifTags import GPSTAGS, TAGS

    try:
        img = Image.open(str(image_path))
        exif_data = img._getexif()
        if exif_data is None:
            return None

        gps_info = {}
        for tag_id, value in exif_data.items():
            tag = TAGS.get(tag_id, tag_id)
            if tag == "GPSInfo":
                for gps_tag_id in value:
                    gps_tag = GPSTAGS.get(gps_tag_id, gps_tag_id)
                    gps_info[gps_tag] = value[gps_tag_id]

        if not gps_info:
            return None

        def _dms_to_decimal(dms: tuple, ref: str) -> float:
            degrees = float(dms[0])
            minutes = float(dms[1])
            seconds = float(dms[2])
            decimal = degrees + minutes / 60 + seconds / 3600
            if ref in ("S", "W"):
                decimal = -decimal
            return decimal

        lat = _dms_to_decimal(
            gps_info["GPSLatitude"],
            gps_info["GPSLatitudeRef"],
        )
        lon = _dms_to_decimal(
            gps_info["GPSLongitude"],
            gps_info["GPSLongitudeRef"],
        )
        return (lat, lon)

    except Exception:
        return None


def compute_class_weights(
    labels: list[int] | np.ndarray,
    n_classes: int,
) -> np.ndarray:
    """Compute inverse-frequency class weights for balanced sampling.

    Returns a weight per class: ``w_c = N / (C × n_c)``.
    """
    counts = np.bincount(np.asarray(labels), minlength=n_classes).astype(float)
    weights = len(labels) / (n_classes * counts + 1e-6)
    return weights


def compute_sample_weights(
    labels: list[int] | np.ndarray,
    n_classes: int,
) -> np.ndarray:
    """Compute per-sample weights for WeightedRandomSampler.

    Each sample gets the inverse-frequency weight of its class.
    """
    cw = compute_class_weights(labels, n_classes)
    return cw[np.asarray(labels)]
