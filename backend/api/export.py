"""OBIS Darwin Core Archive export endpoint.

GET /api/v1/export/obis — Download a DwC-A ZIP of verified sightings.
"""

from __future__ import annotations

import logging
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

from backend.services import obis_export

router = APIRouter(prefix="/export", tags=["export"])
logger = logging.getLogger(__name__)


@router.get(
    "/obis",
    response_class=Response,
    responses={
        200: {
            "content": {"application/zip": {}},
            "description": (
                "Darwin Core Archive (ZIP) containing "
                "occurrence.csv, emof.csv, meta.xml, eml.xml"
            ),
        },
    },
    summary="Export verified sightings as OBIS DwC-A",
)
def export_obis_dwca(
    since: datetime | None = Query(  # noqa: B008
        None,
        description=(
            "Only include sightings created on or after this ISO-8601 datetime"
        ),
    ),
    until: datetime | None = Query(  # noqa: B008
        None,
        description=(
            "Only include sightings created on or before this ISO-8601 datetime"
        ),
    ),
):
    """Generate and download a Darwin Core Archive.

    The archive contains all verified community sightings
    formatted for upload to OBIS (obis.org).  Only sightings
    with ``verification_status = 'verified'`` or
    ``moderator_status = 'verified'`` are included.

    The ZIP contains:

    - **occurrence.csv** — Core occurrence records with
      DwC standard terms (scientificName, eventDate,
      coordinates, etc.)
    - **emof.csv** — Extended Measurement or Fact extension
      (sea state, group size, observation platform)
    - **meta.xml** — Archive descriptor
    - **eml.xml** — EML 2.1.1 dataset metadata
    """
    try:
        zip_bytes, n_records = obis_export.generate_dwca(
            since=since,
            until=until,
        )
    except Exception as exc:
        logger.exception("DwC-A export failed")
        raise HTTPException(500, "Export generation failed") from exc

    if n_records == 0:
        raise HTTPException(
            404,
            "No verified sightings found for the given date range.",
        )

    filename = "marine_risk_mapping_dwca.zip"
    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={
            "Content-Disposition": (f'attachment; filename="{filename}"'),
        },
    )
