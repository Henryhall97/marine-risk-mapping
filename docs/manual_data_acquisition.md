# Manual Data Acquisition Guide

Some datasets cannot be downloaded programmatically and must be
acquired manually before running the pipeline. This document
describes each one and where to place it.

> **Tip:** After obtaining all three, run the automated pipeline
> from the project root:
> ```bash
> uv run python -m pipeline.ingestion.download_cetaceans   # filters OBIS → cetacean parquet
> uv run python -m pipeline.ingestion.parse_ship_strikes   # parses PDF → CSV
> ```

---

## 1. GEBCO Bathymetry Raster

| Field | Value |
|-------|-------|
| **What** | GEBCO 2025 gridded bathymetry (GeoTIFF subset) |
| **Why manual** | GEBCO requires accepting a licence; large regional extracts must be requested via their web tool or emailed |
| **Source** | https://www.gebco.net/data_and_products/gridded_bathymetry_data/ |
| **Expected path** | `data/raw/bathymetry/gebco_2025_n52.0_s-2.0_w-180.0_e-59.0.tif` |

### Steps

1. Go to https://download.gebco.net/ (GEBCO Grid download tool).
2. Select the bounding box: **N 52.0, S -2.0, W -180.0, E -59.0**.
3. Choose format **GeoTIFF** and grid **GEBCO_2025**.
4. Submit the request. For large extracts GEBCO emails a download link.
5. Place the downloaded `.tif` file at the path above.

### Verification

```bash
gdalinfo data/raw/bathymetry/gebco_2025_n52.0_s-2.0_w-180.0_e-59.0.tif | head -5
# Should show a GeoTIFF with EPSG:4326
```

---

## 2. NOAA Ship Strike PDF

| Field | Value |
|-------|-------|
| **What** | "Confirmed and Possible Ship Strikes to Large Whales" (Jensen & Silber) |
| **Why manual** | PDF hosted on NOAA InPort; no stable direct-download URL |
| **Source** | NOAA InPort Record 23127 — https://www.fisheries.noaa.gov/inport/item/23127 |
| **Expected path** | `data/raw/cetacean/noaa_23127_DS1.pdf` |

### Steps

1. Go to https://www.fisheries.noaa.gov/inport/item/23127
2. Navigate to **Data Downloads** and download `noaa_23127_DS1.pdf`.
3. Place it at the path above.

### What happens next

`pipeline/ingestion/parse_ship_strikes.py` reads this PDF, extracts
~261 incident records from the data pages, converts degree-minute
coordinates to decimal degrees, and writes:

```
data/processed/ship_strikes/ship_strikes.csv
```

---

## 3. OBIS Occurrence Parquet Files

| Field | Value |
|-------|-------|
| **What** | Full OBIS occurrence export (~6,800 parquet files, ~180 GB) |
| **Why manual** | The full export is hosted on AWS Open Data; downloading via the OBIS API would take days |
| **Source** | `s3://obis-open-data/occurrence/` (public, no credentials needed) |
| **Expected path** | `data/raw/occurrence/*.parquet` (~6,791 files) |

### Steps

1. Install the AWS CLI if you don't have it: https://aws.amazon.com/cli/
2. Sync the full occurrence dataset (this is ~180 GB):

```bash
cd data/raw
aws s3 sync --no-sign-request s3://obis-open-data/occurrence/ ./occurrence/
```

3. This will create `data/raw/occurrence/` with ~6,800 parquet files.

### What happens next

`pipeline/ingestion/download_cetaceans.py` uses DuckDB to query
these parquets with pushdown predicates, filtering to:

- Order = Cetartiodactyla (whales, dolphins, porpoises)
- Study bounding box (lat 2°S–52°N, lon 180°W–59°W)
- Presence records only (no absences, no dropped records)

The filtered output (~364K sightings) is written to:

```
data/raw/cetacean/us_cetacean_sightings.parquet
```

### Space-saving alternative

If 180 GB is too large, you can download a subset and filter
locally. The pipeline only needs the final
`us_cetacean_sightings.parquet` file to proceed.

---

## Quick Checklist

Before running the pipeline, verify these files exist:

```bash
# Bathymetry raster
ls -lh data/raw/bathymetry/gebco_2025_n49.0_s24.0_w-130.0_e-65.0.tif

# Ship strike PDF
ls -lh data/raw/cetacean/noaa_23127_DS1.pdf

# OBIS occurrence parquets (should be ~6,800 files)
ls data/raw/occurrence/*.parquet | wc -l
```

If any are missing, follow the steps above. All other datasets
are downloaded automatically by the ingestion scripts.
