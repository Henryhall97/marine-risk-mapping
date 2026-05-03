"""OBIS Darwin Core Archive export service.

Generates DwC-A ZIP archives from verified sighting submissions,
formatted for upload to the Ocean Biodiversity Information System.

DwC-A structure::

    dwca.zip/
        occurrence.csv   — core occurrence records (DwC terms)
        emof.csv         — Extended Measurement or Fact extension
        meta.xml         — archive descriptor
        eml.xml          — dataset metadata (EML 2.1.1)
"""

from __future__ import annotations

import csv
import io
import logging
import zipfile
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from backend.services.database import fetch_all

log = logging.getLogger(__name__)

# ── DwC column mapping ───────────────────────────────────────

# OBIS required + recommended DwC terms for occurrence core
_DWC_COLUMNS = [
    "occurrenceID",
    "eventDate",
    "decimalLatitude",
    "decimalLongitude",
    "scientificName",
    "scientificNameID",
    "occurrenceStatus",
    "basisOfRecord",
    "coordinateUncertaintyInMeters",
    "individualCount",
    "lifeStage",
    "behavior",
    "occurrenceRemarks",
    "recordedBy",
    "institutionCode",
    "collectionCode",
    "datasetName",
    "modified",
]

# eMoF columns (Extended Measurement or Fact)
_EMOF_COLUMNS = [
    "occurrenceID",
    "measurementType",
    "measurementValue",
    "measurementUnit",
    "measurementTypeID",
    "measurementUnitID",
]

# NERC / BODC vocabulary URIs for eMoF
_BEAUFORT_TYPE_ID = "http://vocab.nerc.ac.uk/collection/P01/current/WMOCWFBF/"
_BEAUFORT_UNIT_ID = "http://vocab.nerc.ac.uk/collection/P06/current/UUUU/"
_GROUP_SIZE_TYPE_ID = "http://vocab.nerc.ac.uk/collection/P01/current/OCOUNT01/"
_PLATFORM_TYPE_ID = "http://vocab.nerc.ac.uk/collection/W03/current/"


def _query_verified_sightings(
    *,
    since: datetime | None = None,
    until: datetime | None = None,
) -> list[dict[str, Any]]:
    """Fetch verified sightings suitable for OBIS export."""
    conditions = ["(verification_status = 'verified' OR moderator_status = 'verified')"]
    params: list[Any] = []

    if since:
        conditions.append("s.created_at >= %s")
        params.append(since)
    if until:
        conditions.append("s.created_at <= %s")
        params.append(until)

    where = " AND ".join(conditions)

    query = f"""
        SELECT
            s.id::text           AS submission_id,
            s.created_at,
            s.sighting_datetime,
            s.lat,
            s.lon,
            s.coordinate_uncertainty_m,
            s.scientific_name,
            s.aphia_id,
            s.species_guess,
            s.model_species,
            s.model_source,
            s.description,
            s.group_size,
            s.behavior,
            s.life_stage,
            s.calf_present,
            s.sea_state_beaufort,
            s.observation_platform,
            s.interaction_type,
            u.display_name       AS recorded_by
        FROM sighting_submissions s
        LEFT JOIN users u ON u.id = s.user_id
        WHERE {where}
        ORDER BY s.created_at
    """
    return fetch_all(query, tuple(params))


def _make_occurrence_id(submission_id: str) -> str:
    """Build a globally unique occurrenceID from submission UUID."""
    return f"urn:uuid:{submission_id}"


def _build_scientific_name_id(aphia_id: int | None) -> str:
    """Build WoRMS LSID from AphiaID."""
    if aphia_id:
        return f"urn:lsid:marinespecies.org:taxname:{aphia_id}"
    return ""


def _format_event_date(row: dict[str, Any]) -> str:
    """Extract ISO-8601 eventDate from sighting or created_at."""
    dt = row.get("sighting_datetime") or row.get("created_at")
    if dt is None:
        return ""
    if hasattr(dt, "isoformat"):
        return dt.isoformat().replace("+00:00", "Z")
    return str(dt)


def _map_life_stage(raw: str | None) -> str:
    """Map life stage to DwC controlled vocabulary."""
    if not raw:
        return ""
    mapping = {
        "adult": "adult",
        "juvenile": "juvenile",
        "calf": "juvenile",  # DwC doesn't have "calf"
        "unknown": "",
    }
    return mapping.get(raw.lower(), raw)


def _build_occurrence_row(
    row: dict[str, Any],
    dataset_name: str,
) -> dict[str, str]:
    """Convert a sighting row to a DwC occurrence record."""
    occ_id = _make_occurrence_id(row["submission_id"])

    # Prefer resolved scientific_name, fall back to model/user
    sci_name = (
        row.get("scientific_name")
        or row.get("model_species")
        or row.get("species_guess")
        or ""
    )

    remarks_parts = []
    if row.get("description"):
        remarks_parts.append(row["description"])
    if row.get("interaction_type"):
        remarks_parts.append(f"interaction: {row['interaction_type']}")
    if row.get("calf_present"):
        remarks_parts.append("calf present")
    if row.get("model_source"):
        remarks_parts.append(f"species ID source: {row['model_source']}")

    return {
        "occurrenceID": occ_id,
        "eventDate": _format_event_date(row),
        "decimalLatitude": str(row.get("lat") or ""),
        "decimalLongitude": str(row.get("lon") or ""),
        "scientificName": sci_name,
        "scientificNameID": _build_scientific_name_id(row.get("aphia_id")),
        "occurrenceStatus": "present",
        "basisOfRecord": "HumanObservation",
        "coordinateUncertaintyInMeters": str(row.get("coordinate_uncertainty_m") or ""),
        "individualCount": str(row.get("group_size") or ""),
        "lifeStage": _map_life_stage(row.get("life_stage")),
        "behavior": row.get("behavior") or "",
        "occurrenceRemarks": "; ".join(remarks_parts),
        "recordedBy": row.get("recorded_by") or "",
        "institutionCode": "MarineRiskMapping",
        "collectionCode": "CommunityWhaleWatch",
        "datasetName": dataset_name,
        "modified": (datetime.now(UTC).isoformat().replace("+00:00", "Z")),
    }


def _build_emof_rows(
    row: dict[str, Any],
) -> list[dict[str, str]]:
    """Build eMoF measurement rows for a sighting."""
    occ_id = _make_occurrence_id(row["submission_id"])
    measurements: list[dict[str, str]] = []

    if row.get("sea_state_beaufort") is not None:
        measurements.append(
            {
                "occurrenceID": occ_id,
                "measurementType": "Beaufort wind force",
                "measurementValue": str(row["sea_state_beaufort"]),
                "measurementUnit": "Beaufort scale",
                "measurementTypeID": _BEAUFORT_TYPE_ID,
                "measurementUnitID": _BEAUFORT_UNIT_ID,
            }
        )

    if row.get("group_size") is not None:
        measurements.append(
            {
                "occurrenceID": occ_id,
                "measurementType": "Organism count",
                "measurementValue": str(row["group_size"]),
                "measurementUnit": "individuals",
                "measurementTypeID": _GROUP_SIZE_TYPE_ID,
                "measurementUnitID": "",
            }
        )

    if row.get("observation_platform"):
        measurements.append(
            {
                "occurrenceID": occ_id,
                "measurementType": "Sampling platform",
                "measurementValue": row["observation_platform"],
                "measurementUnit": "",
                "measurementTypeID": _PLATFORM_TYPE_ID,
                "measurementUnitID": "",
            }
        )

    return measurements


def _build_meta_xml() -> str:
    """Generate meta.xml archive descriptor."""
    return """<?xml version="1.0" encoding="UTF-8"?>
<archive xmlns="http://rs.tdwg.org/dwc/text/"
         metadata="eml.xml">
  <core encoding="UTF-8"
        linesTerminatedBy="\\n"
        fieldsTerminatedBy=","
        fieldsEnclosedBy="&quot;"
        ignoreHeaderLines="1"
        rowType="http://rs.tdwg.org/dwc/terms/Occurrence">
    <files><location>occurrence.csv</location></files>
    <id index="0"/>
    <field index="0" term="http://rs.tdwg.org/dwc/terms/occurrenceID"/>
    <field index="1" term="http://rs.tdwg.org/dwc/terms/eventDate"/>
    <field index="2" term="http://rs.tdwg.org/dwc/terms/decimalLatitude"/>
    <field index="3" term="http://rs.tdwg.org/dwc/terms/decimalLongitude"/>
    <field index="4" term="http://rs.tdwg.org/dwc/terms/scientificName"/>
    <field index="5" term="http://rs.tdwg.org/dwc/terms/scientificNameID"/>
    <field index="6" term="http://rs.tdwg.org/dwc/terms/occurrenceStatus"/>
    <field index="7" term="http://rs.tdwg.org/dwc/terms/basisOfRecord"/>
    <field index="8" term="http://rs.tdwg.org/dwc/terms/coordinateUncertaintyInMeters"/>
    <field index="9" term="http://rs.tdwg.org/dwc/terms/individualCount"/>
    <field index="10" term="http://rs.tdwg.org/dwc/terms/lifeStage"/>
    <field index="11" term="http://rs.tdwg.org/dwc/terms/behavior"/>
    <field index="12" term="http://rs.tdwg.org/dwc/terms/occurrenceRemarks"/>
    <field index="13" term="http://rs.tdwg.org/dwc/terms/recordedBy"/>
    <field index="14" term="http://rs.tdwg.org/dwc/terms/institutionCode"/>
    <field index="15" term="http://rs.tdwg.org/dwc/terms/collectionCode"/>
    <field index="16" term="http://rs.tdwg.org/dwc/terms/datasetName"/>
    <field index="17" term="http://purl.org/dc/terms/modified"/>
  </core>
  <extension encoding="UTF-8"
             linesTerminatedBy="\\n"
             fieldsTerminatedBy=","
             fieldsEnclosedBy="&quot;"
             ignoreHeaderLines="1"
             rowType="http://rs.iobis.org/obis/terms/ExtendedMeasurementOrFact">
    <files><location>emof.csv</location></files>
    <coreid index="0"/>
    <field index="0" term="http://rs.tdwg.org/dwc/terms/occurrenceID"/>
    <field index="1" term="http://rs.iobis.org/obis/terms/measurementType"/>
    <field index="2" term="http://rs.iobis.org/obis/terms/measurementValue"/>
    <field index="3" term="http://rs.iobis.org/obis/terms/measurementUnit"/>
    <field index="4" term="http://rs.iobis.org/obis/terms/measurementTypeID"/>
    <field index="5" term="http://rs.iobis.org/obis/terms/measurementUnitID"/>
  </extension>
</archive>"""


def _build_eml_xml(
    *,
    dataset_name: str,
    n_records: int,
    export_date: str,
) -> str:
    """Generate EML 2.1.1 dataset metadata."""
    dataset_id = str(uuid4())
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<eml:eml xmlns:eml="eml://ecoinformatics.org/eml-2.1.1"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="eml://ecoinformatics.org/eml-2.1.1 eml.xsd"
         packageId="{dataset_id}" system="MarineRiskMapping">
  <dataset>
    <title>{dataset_name}</title>
    <creator>
      <organizationName>Marine Risk Mapping Project</organizationName>
    </creator>
    <metadataProvider>
      <organizationName>Marine Risk Mapping Project</organizationName>
    </metadataProvider>
    <pubDate>{export_date}</pubDate>
    <language>eng</language>
    <abstract>
      <para>Community-contributed whale and cetacean sighting records
      collected via the Marine Risk Mapping platform. Observations are
      submitted by citizen scientists and verified through community
      consensus and/or moderator review before inclusion in this
      dataset. Species identifications are supported by AI photo and
      audio classifiers and cross-referenced with the WoRMS taxonomic
      backbone. {n_records} occurrence records.</para>
    </abstract>
    <intellectualRights>
      <para>This work is licensed under a Creative Commons
      Attribution 4.0 International License (CC-BY 4.0).</para>
    </intellectualRights>
    <contact>
      <organizationName>Marine Risk Mapping Project</organizationName>
    </contact>
  </dataset>
</eml:eml>"""


def generate_dwca(
    *,
    since: datetime | None = None,
    until: datetime | None = None,
    dataset_name: str = ("Marine Risk Mapping — Community Whale Sightings"),
) -> tuple[bytes, int]:
    """Generate a DwC-A ZIP archive.

    Returns ``(zip_bytes, record_count)``.
    """
    rows = _query_verified_sightings(since=since, until=until)
    n = len(rows)
    log.info("Exporting %d verified sightings as DwC-A", n)

    export_date = datetime.now(UTC).strftime("%Y-%m-%d")

    # Build CSV content
    occ_buf = io.StringIO()
    occ_writer = csv.DictWriter(occ_buf, fieldnames=_DWC_COLUMNS)
    occ_writer.writeheader()

    emof_buf = io.StringIO()
    emof_writer = csv.DictWriter(emof_buf, fieldnames=_EMOF_COLUMNS)
    emof_writer.writeheader()

    for row in rows:
        occ_row = _build_occurrence_row(row, dataset_name)
        occ_writer.writerow(occ_row)

        for m in _build_emof_rows(row):
            emof_writer.writerow(m)

    # Build ZIP
    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("occurrence.csv", occ_buf.getvalue())
        zf.writestr("emof.csv", emof_buf.getvalue())
        zf.writestr("meta.xml", _build_meta_xml())
        zf.writestr(
            "eml.xml",
            _build_eml_xml(
                dataset_name=dataset_name,
                n_records=n,
                export_date=export_date,
            ),
        )

    return zip_buf.getvalue(), n
