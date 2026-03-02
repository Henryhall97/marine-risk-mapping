"""Download Nisi et al. (2024) whale-ship collision risk data from GitHub.

Downloads the publicly available data from the Science paper:
    Nisi, A.C., Welch, H., Brodie, S., et al. (2024).
    "Ship collision risk threatens whales across the world's oceans."
    Science 386(6724): 870-875. DOI: 10.1126/science.adp1950

Repository: https://github.com/annanisi/Global_Whale_Ship

Key datasets downloaded:
  - global_whale_ship_risk.csv  (1° grid, 37 cols: risk, hotspots, management)
  - shipping_density.csv        (1° grid, AIS shipping density 2017-2022)
  - blue_whale_isdm_data.csv    (presence/absence + environmental covariates)
  - fin_whale_isdm_data.csv
  - humpback_whale_isdm_data.csv
  - sperm_whale_isdm_data.csv

Run with:
    uv run python -m pipeline.ingestion.download_nisi_2024
"""

import logging
import urllib.request
from pathlib import Path

# ── Configuration ────────────────────────────────────────
GITHUB_RAW_BASE = "https://raw.githubusercontent.com/annanisi/Global_Whale_Ship/main"

OUTPUT_DIR = Path("data/raw/nisi_2024")

# Files to download from the repository
FILES = [
    # Primary risk grid (the main output of the paper)
    "global_whale_ship_risk.csv",
    # Global AIS shipping density at 1° resolution
    "shipping_density.csv",
    # Species distribution model input data (presence/absence + covariates)
    "blue_whale_isdm_data.csv",
    "fin_whale_isdm_data.csv",
    "humpback_whale_isdm_data.csv",
    "sperm_whale_isdm_data.csv",
    # R script for fitting integrated species distribution models
    "fit_ISDM.R",
]

# Monthly environmental prediction grids for North Pacific (0.25° resolution)
PREDICTION_FILES = [
    f"prediction_data_north_pacific/prediction_data_{m}.csv" for m in range(1, 13)
]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def download_file(url: str, dest: Path) -> bool:
    """Download a single file from URL to destination path."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        size_mb = dest.stat().st_size / (1024 * 1024)
        logger.info("  Already exists: %s (%.1f MB)", dest.name, size_mb)
        return True
    try:
        logger.info("  Downloading: %s", url.split("/")[-1])
        urllib.request.urlretrieve(url, dest)
        size_mb = dest.stat().st_size / (1024 * 1024)
        logger.info("  Saved: %s (%.1f MB)", dest, size_mb)
        return True
    except Exception as e:
        logger.error("  Failed to download %s: %s", url, e)
        return False


def main() -> None:
    """Download all Nisi et al. (2024) data files."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    logger.info("=" * 60)
    logger.info("Downloading Nisi et al. (2024) data from GitHub")
    logger.info("  Source: %s", GITHUB_RAW_BASE)
    logger.info("  Destination: %s", OUTPUT_DIR)
    logger.info("=" * 60)

    # ── Download primary data files ──────────────────────
    logger.info("\n--- Primary data files ---")
    success_count = 0
    fail_count = 0
    for filename in FILES:
        url = f"{GITHUB_RAW_BASE}/{filename}"
        dest = OUTPUT_DIR / filename
        if download_file(url, dest):
            success_count += 1
        else:
            fail_count += 1

    # ── Download prediction grid files ───────────────────
    logger.info("\n--- North Pacific prediction grids (monthly) ---")
    for filename in PREDICTION_FILES:
        url = f"{GITHUB_RAW_BASE}/{filename}"
        dest = OUTPUT_DIR / filename
        if download_file(url, dest):
            success_count += 1
        else:
            fail_count += 1

    # ── Summary ──────────────────────────────────────────
    logger.info("\n" + "=" * 60)
    logger.info("Download complete: %d succeeded, %d failed", success_count, fail_count)

    # Show file sizes
    total_mb = 0.0
    for f in sorted(OUTPUT_DIR.rglob("*.csv")):
        size_mb = f.stat().st_size / (1024 * 1024)
        total_mb += size_mb
    r_files = list(OUTPUT_DIR.rglob("*.R"))
    for f in r_files:
        total_mb += f.stat().st_size / (1024 * 1024)

    logger.info("Total data size: %.1f MB", total_mb)
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
