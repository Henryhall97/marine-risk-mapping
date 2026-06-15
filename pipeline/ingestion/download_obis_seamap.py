"""Download OBIS-SEAMAP survey *observations* via the OBIS API.

Scope and honest limits
-----------------------
OBIS-SEAMAP (Duke MGEL) hosts the AMAPPS Northeast + Southeast aerial
and shipboard cruises (2010-2023) under provider 671 (Beth Josephson,
NOAA Fisheries NEFSC). Those datasets are pushed to the global OBIS
node, so the **sighting/observation records** can be pulled
programmatically by dataset DOI from the OBIS API.

This script downloads ONLY the observation layer (per-sighting
lat/lon, date, species, group size). That is enough for a
presence/SDM cross-check and to confirm survey coverage, but it is
**not** the distance-sampling input the IWC gate needs:

* On-effort tracklines (segmentable effort) are downloadable on the
  OBIS-SEAMAP *Dataset Page* only, via the "Complete Set of Dataset"
  option behind the download disclaimer - NOT exposed through the
  scriptable minimum-attribute export or the OBIS API.
* Per-sighting **perpendicular distances** are an "other attribute"
  under the CC-BY minimum-attribute policy and generally require
  contributor permission.

Both of those still route back to the direct request to
Beth Josephson (elizabeth.josephson@noaa.gov / OBIS-SEAMAP provider
671). See docs/survey_data_status.md, action #1.

Attribution
-----------
OBIS-SEAMAP Terms of Use require per-dataset citation (DOI) plus the
OBIS-SEAMAP citation. This script writes a citations.csv alongside the
data with the DOI for every dataset downloaded. Do not redistribute
the raw records without consent (see Terms of Use clause 8).

Usage
-----
    uv run python pipeline/ingestion/download_obis_seamap.py --dry-run
    uv run python pipeline/ingestion/download_obis_seamap.py
    uv run python pipeline/ingestion/download_obis_seamap.py \
        --program amapps_ne_aerial
"""

from __future__ import annotations

import argparse
import logging
import time

import httpx
import pandas as pd

from pipeline.config import RAW_DIR

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

OBIS_API = "https://api.obis.org/v3"
SEAMAP_DOI_BASE = "https://seamap.env.duke.edu"
OUTPUT_DIR = RAW_DIR / "survey" / "obis_seamap"

# Page size for the OBIS occurrence cursor (max 10000).
PAGE_SIZE = 10000
REQUEST_TIMEOUT = 60.0

# DwC columns we keep from the OBIS occurrence response. Anything
# missing is filled with NA so the per-dataset frames concatenate.
KEEP_COLUMNS = [
    "id",
    "dataset_id",
    "scientificName",
    "vernacularName",
    "individualCount",
    "decimalLatitude",
    "decimalLongitude",
    "eventDate",
    "year",
    "month",
    "day",
    "basisOfRecord",
    "occurrenceStatus",
    "coordinateUncertaintyInMeters",
    "institutionCode",
    "collectionCode",
    "datasetName",
]

# Provider-671 AMAPPS cruises on OBIS-SEAMAP. Each entry:
#   (seamap_dataset_id, doi_suffix, exact_title)
# DOI = https://doi.org/10.82144/<doi_suffix>
# Landing = https://seamap.env.duke.edu/dataset/<seamap_dataset_id>
PROGRAMS: dict[str, list[tuple[int, str, str]]] = {
    "amapps_ne_aerial": [
        (2310, "d1f47150", "AMAPPS Northeast Aerial Cruise Spring 2023"),
        (2280, "0dab0a2a", "AMAPPS Northeast Aerial Cruise Summer 2021"),
        (2062, "ce66222d", "AMAPPS Northeast Aerial Cruise Fall 2019"),
        (2060, "9b5b87de", "AMAPPS Northeast Aerial Cruise Spring 2019"),
        (1997, "a43a260e", "AMAPPS Northeast Aerial Cruise Spring 2017"),
        (1995, "e7eaab77", "AMAPPS Northeast Aerial Cruise Winter 2017"),
        (1676, "71353745", "AMAPPS Northeast Aerial Cruise Summer 2016"),
        (1381, "ababc77c", "AMAPPS Northeast Aerial Cruise Winter 2014"),
        (1379, "6fab8b55", "AMAPPS Northeast Aerial Cruise Spring 2014"),
        (1247, "5bd77b1d", "AMAPPS Northeast Aerial Cruise Spring 2012"),
        (1245, "dea07d02", "AMAPPS Northeast Aerial Cruise Fall 2012"),
        (1243, "0e79cf1a", "AMAPPS Northeast Aerial Cruise Winter 2011"),
        (1233, "62b3595e", "AMAPPS Northeast Aerial Cruise Summer 2011"),
        (1249, "b18543a8", "AMAPPS Northeast Aerial Cruise Summer 2010"),
    ],
    "amapps_ne_shipboard": [
        (2278, "46695a9e", "AMAPPS Northeast Shipboard Cruise Summer 2021"),
        (1678, "328ed025", "AMAPPS Northeast Shipboard Cruise Summer 2016"),
        (1377, "e629a091", "AMAPPS Northeast Shipboard Cruise Spring 2014"),
        (1271, "98eefea9", "AMAPPS Northeast Shipboard Cruise Summer 2013"),
        (1269, "51704061", "AMAPPS Northeast Shipboard Cruise Summer 2011"),
    ],
    "amapps_se_aerial": [
        (2053, "77bf926a", "AMAPPS Southeast Aerial Cruise Winter 2019-2020"),
        (2036, "00cc08bb", "AMAPPS Southeast Aerial Cruise Spring 2019"),
        (1860, "fbbc93ce", "AMAPPS Southeast Aerial Cruise Spring 2017"),
        (1858, "83f6b512", "AMAPPS Southeast Aerial Cruise Fall 2017"),
        (1856, "d6149251", "AMAPPS Southeast Aerial Cruise Summer 2016"),
        (1854, "0998742a", "AMAPPS Southeast Aerial Cruise Fall 2016"),
        (1852, "14782689", "AMAPPS Southeast Aerial Cruise Winter 2015"),
        (1850, "90851051", "AMAPPS Southeast Aerial Cruise Spring 2014"),
        (1289, "d7e75361", "AMAPPS Southeast Aerial Cruise Winter 2013"),
        (1288, "a07d15d0", "AMAPPS Southeast Aerial Cruise Fall 2012"),
        (1259, "ac88380d", "AMAPPS Southeast Aerial Cruise Spring 2012"),
        (1277, "b75120be", "AMAPPS Southeast Aerial Cruise Winter 2011"),
        (1275, "ba5328ce", "AMAPPS Southeast Aerial Cruise Summer 2011"),
        (1273, "f04b7911", "AMAPPS Southeast Aerial Cruise Summer 2010"),
    ],
    "amapps_se_shipboard": [
        (1974, "a20ffb32", "AMAPPS Southeast Shipboard Cruise Summer 2016"),
    ],
}


def _resolve_obis_dataset_id(client: httpx.Client, title: str) -> str | None:
    """Resolve an OBIS dataset UUID from its exact title.

    OBIS-SEAMAP datasets are mirrored into the global OBIS node. We
    match on the exact (case-insensitive) title to avoid pulling a
    similarly named dataset from another provider.
    """
    resp = client.get(
        f"{OBIS_API}/dataset",
        params={"q": title},
        timeout=REQUEST_TIMEOUT,
    )
    resp.raise_for_status()
    results = resp.json().get("results", [])
    target = title.strip().lower()
    for ds in results:
        if (ds.get("title") or "").strip().lower() == target:
            return ds.get("id")
    # Fall back to the first hit only if it clearly contains the title.
    for ds in results:
        if target in (ds.get("title") or "").strip().lower():
            logger.warning("Fuzzy title match for %r -> %r", title, ds.get("title"))
            return ds.get("id")
    return None


def _download_occurrences(client: httpx.Client, obis_dataset_id: str) -> pd.DataFrame:
    """Page all occurrences for one OBIS dataset via the id cursor."""
    rows: list[dict] = []
    after = None
    while True:
        params = {"datasetid": obis_dataset_id, "size": PAGE_SIZE}
        if after is not None:
            params["after"] = after
        resp = client.get(
            f"{OBIS_API}/occurrence",
            params=params,
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        results = resp.json().get("results", [])
        if not results:
            break
        rows.extend(results)
        after = results[-1].get("id")
        if after is None or len(results) < PAGE_SIZE:
            break
        time.sleep(0.2)  # be polite to the OBIS API
    if not rows:
        return pd.DataFrame(columns=KEEP_COLUMNS)
    frame = pd.DataFrame(rows)
    for col in KEEP_COLUMNS:
        if col not in frame.columns:
            frame[col] = pd.NA
    return frame[KEEP_COLUMNS]


def download_programs(programs: list[str], dry_run: bool = False) -> None:
    """Download (or preview) the requested AMAPPS programs."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    citations: list[dict] = []
    all_frames: list[pd.DataFrame] = []
    accessed = pd.Timestamp.utcnow().date().isoformat()

    with httpx.Client(headers={"User-Agent": "marine-risk-mapping"}) as client:
        for program in programs:
            datasets = PROGRAMS[program]
            logger.info("Program %s: %d datasets", program, len(datasets))
            for seamap_id, doi_suffix, title in datasets:
                doi = f"10.82144/{doi_suffix}"
                obis_id = _resolve_obis_dataset_id(client, title)
                if obis_id is None:
                    logger.warning(
                        "NOT FOUND on OBIS: %r (seamap %d) - request "
                        "directly from provider 671",
                        title,
                        seamap_id,
                    )
                    continue

                if dry_run:
                    logger.info(
                        "[dry-run] %s -> OBIS %s (DOI %s)",
                        title,
                        obis_id,
                        doi,
                    )
                    citations.append(
                        {
                            "seamap_dataset_id": seamap_id,
                            "obis_dataset_id": obis_id,
                            "doi": doi,
                            "title": title,
                            "n_records": None,
                        }
                    )
                    continue

                frame = _download_occurrences(client, obis_id)
                frame["seamap_dataset_id"] = seamap_id
                frame["doi"] = doi
                frame["source_title"] = title
                out = OUTPUT_DIR / f"seamap_{seamap_id}.parquet"
                frame.to_parquet(out, index=False)
                all_frames.append(frame)
                logger.info(
                    "%s: %d records -> %s",
                    title,
                    len(frame),
                    out.name,
                )
                citations.append(
                    {
                        "seamap_dataset_id": seamap_id,
                        "obis_dataset_id": obis_id,
                        "doi": doi,
                        "title": title,
                        "n_records": len(frame),
                    }
                )

    # Write the citation manifest (Terms of Use clause: per-dataset DOI).
    cite_df = pd.DataFrame(citations)
    cite_df["accessed"] = accessed
    cite_df["obis_seamap_citation"] = (
        "Halpin, P.N., A.J. Read, E. Fujioka, et al. 2009. OBIS-SEAMAP. "
        "Oceanography 22(2):104-115."
    )
    cite_path = OUTPUT_DIR / "citations.csv"
    cite_df.to_csv(cite_path, index=False)
    logger.info("Wrote citation manifest -> %s", cite_path)

    if not dry_run and all_frames:
        combined = pd.concat(all_frames, ignore_index=True)
        combined_path = OUTPUT_DIR / "amapps_obis_observations.parquet"
        combined.to_parquet(combined_path, index=False)
        logger.info(
            "Combined %d records across %d datasets -> %s",
            len(combined),
            len(all_frames),
            combined_path.name,
        )
        logger.info(
            "NOTE: these are observations only. Effort tracklines + "
            "perpendicular distances still require the direct request "
            "to provider 671 (Beth Josephson)."
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--program",
        choices=[*PROGRAMS.keys(), "all"],
        default="all",
        help="Which AMAPPS program(s) to download.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Resolve OBIS dataset IDs and write citations only.",
    )
    args = parser.parse_args()

    programs = list(PROGRAMS.keys()) if args.program == "all" else [args.program]
    download_programs(programs, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
