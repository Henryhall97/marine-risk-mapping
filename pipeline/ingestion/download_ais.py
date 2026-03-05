"""Download AIS broadcast point data from MarineCadastre.gov.

Downloads daily GeoParquet files for each year in AIS_YEARS
(configured in pipeline/config.py) from the NOAA Marine Cadastre
Azure storage. Supports resuming interrupted downloads.
"""

import logging
import time
from datetime import date, timedelta

import httpx

from pipeline.config import AIS_RAW_DIR, AIS_YEARS

BASE_URL_TEMPLATE = "https://marinecadastre.gov/downloads/ais{year}"
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


def download_file(
    file_date: date,
    output_dir,
    base_url: str,
    *,
    force: bool = False,
) -> bool:
    """Download a single day's AIS GeoParquet file.

    Args:
        file_date: The date to download data for.
        output_dir: Directory to save the file.
        base_url: Year-specific MarineCadastre base URL.
        force: If True, re-download even if file already exists.

    Returns:
        True if downloaded successfully, False if skipped or failed.
    """
    filename = f"ais-{file_date.isoformat()}.parquet"
    url = f"{base_url}/{filename}"
    output_path = output_dir / filename

    # Skip if already downloaded
    if output_path.exists() and not force:
        logger.info("Skipping %s — already exists", filename)
        return False
    if output_path.exists() and force:
        output_path.unlink()

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


def download_all_ais_data(*, force: bool = False) -> None:
    """Download AIS GeoParquet files for all configured years."""
    AIS_RAW_DIR.mkdir(parents=True, exist_ok=True)

    for year in AIS_YEARS:
        base_url = BASE_URL_TEMPLATE.format(year=year)
        start = date(year, 1, 1)
        end = date(year, 12, 31)
        dates = generate_dates(start, end)
        logger.info("Starting AIS download for %d: %d files", year, len(dates))

        downloaded = 0
        skipped = 0
        failed = 0

        for i, file_date in enumerate(dates, start=1):
            logger.info("Progress: %d/%d (%d)", i, len(dates), year)
            result = download_file(file_date, AIS_RAW_DIR, base_url, force=force)

            if result:
                downloaded += 1
                time.sleep(DELAY_BETWEEN_DOWNLOADS)
            else:
                filename = f"ais-{file_date.isoformat()}.parquet"
                if (AIS_RAW_DIR / filename).exists():
                    skipped += 1
                else:
                    failed += 1

        logger.info(
            "%d complete: %d downloaded, %d skipped, %d failed",
            year,
            downloaded,
            skipped,
            failed,
        )


if __name__ == "__main__":
    import argparse

    _parser = argparse.ArgumentParser(description="Download AIS data")
    _parser.add_argument(
        "--force",
        action="store_true",
        help="Re-download even if files exist",
    )
    _args = _parser.parse_args()
    download_all_ais_data(force=_args.force)
