"""Extract whale sprites from the reference image.

The 5 whales overlap heavily, so we take two approaches:
1. Full composite with transparent bg (the whole illustration)
2. Manual crop regions for the most distinct individual whales
"""

import os

import numpy as np
from PIL import Image
from scipy import ndimage

SRC = "frontend/public/whales_reference.png"
OUT_DIR = "frontend/public/whales"
os.makedirs(OUT_DIR, exist_ok=True)

img = Image.open(SRC)
arr = np.array(img)
H, W = arr.shape[:2]
print(f"Source: {W}x{H}")

# ─── Background removal ───────────────────────────────────────
# Background is dark blue (~[20,49,109] at corners).
# Use color distance from bg + brightness to build alpha mask.
bg_color = np.array([15, 40, 100], dtype=np.float32)
diff = np.sqrt(((arr.astype(np.float32) - bg_color) ** 2).sum(axis=2))
gray = arr.mean(axis=2)

# Whale pixels: either far from bg color OR much brighter
whale_prob = np.clip(diff / 80, 0, 1) * np.clip((gray - 40) / 60, 0, 1)
whale_prob = ndimage.gaussian_filter(whale_prob, sigma=1.0)

# Clean up: remove small specks, fill holes
binary = whale_prob > 0.15
binary = ndimage.binary_opening(binary, iterations=2)
binary = ndimage.binary_closing(binary, iterations=3)

# ─── 1. Full composite with transparent bg ─────────────────
# Crop to content bounds (remove empty margins + bottom watermark)
content_mask = binary[:775, :]  # exclude bottom watermark/text
rows = np.where(content_mask.any(axis=1))[0]
cols = np.where(content_mask.any(axis=0))[0]
if len(rows) > 0 and len(cols) > 0:
    cy0, cy1 = max(0, rows[0] - 5), min(775, rows[-1] + 5)
    cx0, cx1 = max(0, cols[0] - 5), min(W, cols[-1] + 5)
else:
    cy0, cy1, cx0, cx1 = 0, 775, 0, W

crop_full = arr[cy0:cy1, cx0:cx1].copy()
alpha_full = np.clip(whale_prob[cy0:cy1, cx0:cx1] * 280, 0, 255).astype(np.uint8)

rgba_full = np.zeros((cy1 - cy0, cx1 - cx0, 4), dtype=np.uint8)
rgba_full[:, :, :3] = crop_full
rgba_full[:, :, 3] = alpha_full

out = os.path.join(OUT_DIR, "whale_composite.png")
Image.fromarray(rgba_full).save(out)
print(f"Saved full composite: {out} ({cx1 - cx0}x{cy1 - cy0})")

# ─── 2. Manual crop regions for individual whales ──────────
# Based on brightness map analysis, these capture distinct whale poses:
manual_crops = [
    # (name, x0, y0, x1, y1, description)
    ("whale_top", 300, 20, 700, 230, "Top whale - side view swimming right"),
    ("whale_upper_left", 180, 200, 530, 500, "Upper-left whale - angled downward"),
    (
        "whale_center_right",
        420,
        250,
        880,
        480,
        "Center-right whale - horizontal, facing right",
    ),
    ("whale_lower_left", 170, 470, 570, 700, "Lower-left whale - swimming down-left"),
    ("whale_lower_right", 480, 480, 900, 720, "Lower-right whale - swimming right"),
]

for name, x0, y0, x1, y1, desc in manual_crops:
    # Clamp to image bounds
    x0, y0 = max(0, x0), max(0, y0)
    x1, y1 = min(W, x1), min(H, y1)

    crop = arr[y0:y1, x0:x1].copy()
    alpha = np.clip(whale_prob[y0:y1, x0:x1] * 300, 0, 255).astype(np.uint8)

    rgba = np.zeros((y1 - y0, x1 - x0, 4), dtype=np.uint8)
    rgba[:, :, :3] = crop
    rgba[:, :, 3] = alpha

    out = os.path.join(OUT_DIR, f"{name}.png")
    Image.fromarray(rgba).save(out)
    print(f"Saved {name}: {out} ({x1 - x0}x{y1 - y0}) — {desc}")

print(f"\nDone! Files in {OUT_DIR}/")
