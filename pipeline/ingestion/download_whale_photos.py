"""Download whale photo training data from the Happywhale Kaggle dataset.

Downloads the full competition dataset via the Kaggle CLI, applies known
label fixes, filters to the 8 target species, and organises images into
species subdirectories.

Prerequisites:
  - ``kaggle`` Python package installed (``uv add kaggle``)
  - Kaggle API credentials at ``~/.kaggle/kaggle.json``
  - Accepted the Happywhale competition rules on kaggle.com

Output directory: data/raw/whale_photos/{species}/

Usage
-----
    # Download + filter (default)
    uv run python pipeline/ingestion/download_whale_photos.py

    # Download only (skip filtering)
    uv run python pipeline/ingestion/download_whale_photos.py --download-only

    # Filter already-downloaded data
    uv run python pipeline/ingestion/download_whale_photos.py --filter-only

    # Limit images per species (for faster iteration)
    uv run python pipeline/ingestion/download_whale_photos.py \\
        --max-per-species 500
"""

from __future__ import annotations

import argparse
import logging
import shutil
from pathlib import Path

import pandas as pd

from pipeline.config import (
    HAPPYWHALE_LABEL_FIXES,
    PHOTO_MAX_IMAGES_PER_SPECIES,
    PHOTO_OTHER_PER_SPECIES_CAP,
    WHALE_PHOTO_BROAD_TARGET_SPECIES,
    WHALE_PHOTO_RAW_DIR,
    WHALE_PHOTO_TARGET_SPECIES,
)

log = logging.getLogger(__name__)

COMPETITION_NAME = "happy-whale-and-dolphin"
RAW_DOWNLOAD_DIR = WHALE_PHOTO_RAW_DIR / "_kaggle_raw"


# ── Download ────────────────────────────────────────────────


def download_kaggle_dataset(
    output_dir: Path | None = None,
) -> Path:
    """Download the Happywhale competition dataset via Kaggle CLI.

    Returns the path to the extracted download directory.
    """
    output_dir = output_dir or RAW_DOWNLOAD_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    train_csv = output_dir / "train.csv"
    if train_csv.exists():
        log.info(
            "Kaggle data already downloaded at %s — skipping",
            output_dir,
        )
        return output_dir

    log.info("Downloading Happywhale dataset from Kaggle...")
    log.info(
        "Make sure you have accepted the competition rules at "
        "https://www.kaggle.com/competitions/%s/rules",
        COMPETITION_NAME,
    )

    try:
        from kaggle.api.kaggle_api_extended import KaggleApi

        api = KaggleApi()
        api.authenticate()

        # Download competition files
        api.competition_download_files(
            COMPETITION_NAME,
            path=str(output_dir),
            quiet=False,
        )

        # Extract the zip if kaggle downloaded a single zip
        zip_path = output_dir / f"{COMPETITION_NAME}.zip"
        if zip_path.exists():
            import zipfile

            log.info("Extracting %s ...", zip_path.name)
            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(output_dir)
            zip_path.unlink()
            log.info("Extraction complete")

    except ImportError:
        log.error("kaggle package not installed. Run: uv add kaggle")
        raise
    except Exception as exc:
        log.error("Kaggle download failed: %s", exc)
        raise

    log.info(
        "Download complete: %s",
        output_dir,
    )
    return output_dir


# ── Label cleaning & filtering ──────────────────────────────


def load_and_clean_labels(
    download_dir: Path | None = None,
) -> pd.DataFrame:
    """Load train.csv, apply known label fixes, and return cleaned DataFrame.

    Returns DataFrame with columns: image, species, individual_id.
    """
    download_dir = download_dir or RAW_DOWNLOAD_DIR
    train_csv = download_dir / "train.csv"

    if not train_csv.exists():
        raise FileNotFoundError(
            f"train.csv not found at {train_csv}. Run download first."
        )

    df = pd.read_csv(train_csv)
    log.info(
        "Loaded train.csv: %d images, %d species",
        len(df),
        df["species"].nunique(),
    )

    # Apply known label fixes
    n_fixed = 0
    for old_label, new_label in HAPPYWHALE_LABEL_FIXES.items():
        mask = df["species"] == old_label
        count = mask.sum()
        if count > 0:
            df.loc[mask, "species"] = new_label
            n_fixed += count
            log.info(
                "  Label fix: '%s' → '%s' (%d images)",
                old_label,
                new_label,
                count,
            )

    if n_fixed > 0:
        log.info("Total label fixes applied: %d", n_fixed)

    log.info(
        "Species after cleaning: %d unique",
        df["species"].nunique(),
    )
    return df


def filter_target_species(
    df: pd.DataFrame,
    target_species: list[str] | None = None,
    max_per_species: int | None = None,
    other_per_species_cap: int = PHOTO_OTHER_PER_SPECIES_CAP,
) -> pd.DataFrame:
    """Filter DataFrame to target species + stratified other_cetacean.

    Parameters
    ----------
    target_species : list[str] | None
        Species to keep individually.  Defaults to WHALE_PHOTO_TARGET_SPECIES.
    max_per_species : int | None
        Cap images per target species.  None = no cap.
    other_per_species_cap : int
        Max images sampled from each non-target species to build the
        ``other_cetacean`` class (default 250).  Ensures diversity.
    """
    target_species = target_species or WHALE_PHOTO_TARGET_SPECIES

    # ── Target species ───────────────────────────────────────
    target_mask = df["species"].isin(target_species)
    target_df = df[target_mask].copy()

    log.info(
        "Target species: %d / %d images across %d species",
        len(target_df),
        len(df),
        len(target_species),
    )
    for sp in sorted(target_species):
        n = (target_df["species"] == sp).sum()
        log.info("  %-20s %5d images", sp, n)

    # Cap target species
    if max_per_species and max_per_species > 0:
        before = len(target_df)
        target_df = (
            target_df.groupby("species", group_keys=False)
            .apply(
                lambda g: g.sample(
                    n=min(len(g), max_per_species),
                    random_state=42,
                )
            )
            .reset_index(drop=True)
        )
        if len(target_df) < before:
            log.info(
                "Capped targets to %d/species: %d → %d",
                max_per_species,
                before,
                len(target_df),
            )

    # ── Other cetacean (stratified from remaining species) ───
    other_mask = ~target_mask
    other_df = df[other_mask].copy()
    other_species = sorted(other_df["species"].unique())
    log.info(
        "Building other_cetacean from %d non-target species "
        "(%d images, cap %d/species)",
        len(other_species),
        len(other_df),
        other_per_species_cap,
    )

    # Stratified sample: cap each non-target species, then pool
    sampled_parts = []
    for sp in other_species:
        sp_df = other_df[other_df["species"] == sp]
        n_take = min(len(sp_df), other_per_species_cap)
        sampled = sp_df.sample(n=n_take, random_state=42)
        sampled_parts.append(sampled)
        log.info(
            "  %-30s %5d → %5d sampled",
            sp,
            len(sp_df),
            n_take,
        )

    other_combined = pd.concat(sampled_parts, ignore_index=True)
    other_combined["species"] = "other_cetacean"
    log.info(
        "other_cetacean class: %d images from %d species",
        len(other_combined),
        len(other_species),
    )

    # ── Combine ──────────────────────────────────────────────
    result = pd.concat([target_df, other_combined], ignore_index=True)
    log.info(
        "Final dataset: %d images, %d classes",
        len(result),
        result["species"].nunique(),
    )

    return result


def organise_images(
    df: pd.DataFrame,
    download_dir: Path | None = None,
    output_dir: Path | None = None,
) -> pd.DataFrame:
    """Copy filtered images into species subdirectories.

    Creates output_dir/{species}/{image_filename}.

    Returns the DataFrame with an added ``file_path`` column pointing
    to the organised image location.
    """
    download_dir = download_dir or RAW_DOWNLOAD_DIR
    output_dir = output_dir or WHALE_PHOTO_RAW_DIR
    train_images_dir = download_dir / "train_images"

    if not train_images_dir.exists():
        raise FileNotFoundError(
            f"train_images/ not found at {train_images_dir}. "
            "Download and extract the dataset first."
        )

    file_paths = []
    copied = 0
    skipped = 0

    for _, row in df.iterrows():
        species = row["species"]
        image_name = row["image"]

        src = train_images_dir / image_name
        species_dir = output_dir / species
        species_dir.mkdir(parents=True, exist_ok=True)
        dst = species_dir / image_name

        if dst.exists():
            file_paths.append(dst)
            skipped += 1
            continue

        if not src.exists():
            log.warning("Source image not found: %s", src)
            file_paths.append(None)
            continue

        shutil.copy2(src, dst)
        file_paths.append(dst)
        copied += 1

    df = df.copy()
    df["file_path"] = file_paths

    # Drop rows where source image was missing
    n_missing = df["file_path"].isna().sum()
    if n_missing > 0:
        log.warning("%d images not found in source — dropped", n_missing)
        df = df.dropna(subset=["file_path"])

    log.info(
        "Organised images: %d copied, %d already existed, %d missing",
        copied,
        skipped,
        n_missing,
    )

    # Save manifest
    manifest_path = output_dir / "training_manifest.csv"
    df.to_csv(manifest_path, index=False)
    log.info("Saved manifest: %s (%d rows)", manifest_path, len(df))

    return df


# ── Summary ─────────────────────────────────────────────────


def print_dataset_summary(df: pd.DataFrame) -> None:
    """Log a summary of the prepared dataset."""
    log.info("\n=== Whale Photo Dataset Summary ===")
    log.info("Total images: %d", len(df))
    log.info("Species: %d", df["species"].nunique())
    log.info("")
    log.info("%-20s %7s", "Species", "Images")
    log.info("-" * 30)
    for sp in sorted(df["species"].unique()):
        n = (df["species"] == sp).sum()
        log.info("%-20s %7d", sp, n)
    log.info("-" * 30)

    if "individual_id" in df.columns:
        log.info(
            "Unique individuals: %d",
            df["individual_id"].nunique(),
        )


# ── CLI ─────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Download and prepare Happywhale training data "
            "for whale photo species classification."
        ),
    )
    parser.add_argument(
        "--download-only",
        action="store_true",
        help="Download from Kaggle but skip filtering",
    )
    parser.add_argument(
        "--filter-only",
        action="store_true",
        help=("Filter already-downloaded data (skip Kaggle download)"),
    )
    parser.add_argument(
        "--max-per-species",
        type=int,
        default=PHOTO_MAX_IMAGES_PER_SPECIES,
        help=(f"Max images per species (default: {PHOTO_MAX_IMAGES_PER_SPECIES})"),
    )
    parser.add_argument(
        "--stage",
        choices=["critical", "broad"],
        default="critical",
        help=(
            "Download stage: 'critical' filters to the 7 ESA-listed large-whale "
            "species (default). 'broad' includes ~10 additional dolphin/porpoise "
            "species available in the Happywhale dataset."
        ),
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%H:%M:%S",
    )

    # Step 1: Download
    if not args.filter_only:
        download_kaggle_dataset()

    if args.download_only:
        log.info("Download complete — exiting (--download-only)")
        return

    # Step 2: Clean labels
    df = load_and_clean_labels()

    # Step 3: Filter to target species
    target_species = (
        WHALE_PHOTO_BROAD_TARGET_SPECIES
        if args.stage == "broad"
        else WHALE_PHOTO_TARGET_SPECIES
    )
    df = filter_target_species(
        df,
        target_species=target_species,
        max_per_species=args.max_per_species,
    )

    # Step 4: Organise into species directories
    df = organise_images(df)

    # Step 5: Summary
    print_dataset_summary(df)


if __name__ == "__main__":
    main()
