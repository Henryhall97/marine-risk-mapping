"""Download AIS broadcast point data from MarineCadastre.gov.

Downloads daily GeoParquet files for 2024 from the NOAA Marine Cadastre
Azure storage. Supports resuming interrupted downloads.
"""

import logging
import time
from datetime import date, timedelta
from pathlib import Path

import httpx

BASE_URL = "https://marinecadastre.gov/downloads/ais2024"
OUTPUT_DIR = Path("data/raw/ais")
START_DATE = date(2024, 1, 1)
END_DATE = date(2024, 12, 31)
CHUNK_SIZE = 65536  # 64KB chunks for download
DELAY_BETWEEN_DOWNLOADS = 1.0  # seconds, be polite to NOAA servers

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def generate_dates(start: date, end: date) -> list[date]:
    """Generate a list of dates from start to end (inclusive)."""
    dates = []
    current = start
    while current <= end:
        dates.append(current)
        current += timedelta(days=1)
    return dates


def download_file(file_date: date, output_dir: Path) -> bool:
    """Download a single day's AIS GeoParquet file.

    Args:
        file_date: The date to download data for.
        output_dir: Directory to save the file.

    Returns:
        True if downloaded successfully, False if skipped or failed.
    """
    filename = f"ais-{file_date.isoformat()}.parquet"
    url = f"{BASE_URL}/{filename}"
    output_path = output_dir / filename

    # Skip if already downloaded
    if output_path.exists():
        logger.info("Skipping %s — already exists", filename)
        return False

    logger.info("Downloading %s", filename)

    try:
        with httpx.stream("GET", url, follow_redirects=True, timeout=300) as response:
            response.raise_for_status()
            with open(output_path, "wb") as f:
                for chunk in response.iter_bytes(chunk_size=CHUNK_SIZE):
                    f.write(chunk)

        size_mb = output_path.stat().st_size / 1e6
        logger.info("Saved %s (%.1f MB)", filename, size_mb)
        return True

    except httpx.HTTPStatusError as e:
        logger.error("HTTP error for %s: %s", filename, e.response.status_code)
        return False

    except httpx.RequestError as e:
        logger.error("Request failed for %s: %s", filename, e)
        # Remove partial file if download failed mid-way
        if output_path.exists():
            output_path.unlink()
        return False


def download_all_ais_data() -> None:
    """Download all AIS GeoParquet files for 2024."""
    # Create output directory
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Generate list of dates to download
    dates = generate_dates(START_DATE, END_DATE)
    logger.info("Starting AIS download: %d files", len(dates))

    downloaded = 0
    skipped = 0
    failed = 0

    for i, file_date in enumerate(dates, start=1):
        logger.info("Progress: %d/%d", i, len(dates))
        result = download_file(file_date, OUTPUT_DIR)

        if result:
            downloaded += 1
            time.sleep(DELAY_BETWEEN_DOWNLOADS)
        else:
            # Check if it was skipped (exists) or failed (doesn't exist)
            filename = f"ais-{file_date.isoformat()}.parquet"
            if (OUTPUT_DIR / filename).exists():
                skipped += 1
            else:
                failed += 1

    logger.info(
        "Download complete: %d downloaded, %d skipped, %d failed",
        downloaded,
        skipped,
        failed,
    )


if __name__ == "__main__":
    download_all_ais_data()
