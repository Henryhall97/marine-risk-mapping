"""Sighting report service — orchestrates photo + audio classifiers + risk.

Delegates to the existing photo and audio services for classification,
then enriches with H3 risk context from fct_collision_risk via the
layers service.
"""

from __future__ import annotations

import logging
from typing import Any

import h3

from backend.services import audio as audio_svc
from backend.services import photo as photo_svc
from backend.services.database import fetch_one

log = logging.getLogger(__name__)

# ── Species-name normalisation ──────────────────────────────

# The photo and audio classifiers may return slightly different
# species label formats.  Normalise to a canonical set so the
# species assessment comparison works correctly.

_CANONICAL_SPECIES: dict[str, str] = {
    "right_whale": "right_whale",
    "humpback_whale": "humpback_whale",
    "fin_whale": "fin_whale",
    "blue_whale": "blue_whale",
    "sperm_whale": "sperm_whale",
    "minke_whale": "minke_whale",
    "sei_whale": "sei_whale",
    "killer_whale": "killer_whale",
    "other_cetacean": "other_cetacean",
    "unknown_whale": "unknown_whale",
}


def _normalise_species(name: str) -> str:
    """Map a classifier label to a canonical species name."""
    return _CANONICAL_SPECIES.get(name, name)


# ── Risk lookup ─────────────────────────────────────────────

_H3_RESOLUTION = 7


def _coords_to_h3(lat: float, lon: float) -> int:
    """Convert WGS-84 coords to an H3 cell BIGINT."""
    hex_str = h3.latlng_to_cell(lat, lon, _H3_RESOLUTION)
    return int(hex_str, 16)


def get_cell_risk(h3_cell: int) -> dict[str, Any] | None:
    """Fetch risk summary for an H3 cell from fct_collision_risk."""
    query = (
        "SELECT h3_cell, risk_score, risk_category, "
        "  traffic_score, cetacean_score, proximity_score, "
        "  strike_score, habitat_score, protection_gap, "
        "  reference_risk_score "
        "FROM fct_collision_risk WHERE h3_cell = %s"
    )
    return fetch_one(query, (h3_cell,))


# ── Advisory generation ─────────────────────────────────────

_PROTECTED_SPECIES = {
    "right_whale",
    "humpback_whale",
    "fin_whale",
    "blue_whale",
    "sei_whale",
    "sperm_whale",
}

_SPECIES_DISPLAY = {
    "right_whale": "North Atlantic right whale",
    "humpback_whale": "humpback whale",
    "fin_whale": "fin whale",
    "blue_whale": "blue whale",
    "sperm_whale": "sperm whale",
    "minke_whale": "minke whale",
    "sei_whale": "sei whale",
    "killer_whale": "killer whale",
    "other_cetacean": "unidentified cetacean",
    "unknown_whale": "unidentified whale",
}


def _generate_advisory(
    species: str | None,
    risk_category: str | None,
    interaction_type: str | None,
) -> dict[str, str]:
    """Build a plain-language risk advisory.

    Returns dict with 'level' and 'message' keys.
    """
    display = _SPECIES_DISPLAY.get(species or "", species or "unknown")
    is_protected = species in _PROTECTED_SPECIES

    # Determine advisory level from risk category
    level_map = {
        "critical": "critical",
        "high": "high",
        "medium": "moderate",
        "low": "low",
    }
    level = level_map.get(risk_category or "low", "low")

    # Escalate for protected species or active strikes
    if is_protected and level in ("low", "moderate"):
        level = "moderate" if level == "low" else "high"
    if interaction_type in ("strike", "entanglement", "near_miss"):
        level = "critical"

    # Build message
    parts: list[str] = []

    if level == "critical":
        parts.append(f"CRITICAL: {display} detected in a high-risk area.")
    elif level == "high":
        parts.append(f"HIGH RISK: {display} identified in an elevated-risk zone.")
    elif level == "moderate":
        parts.append(f"MODERATE: {display} observed — exercise caution.")
    else:
        parts.append(f"LOW RISK: {display} sighting recorded.")

    if is_protected:
        parts.append(
            "This is an ESA/MMPA-protected species. "
            "Maintain ≥500 yd distance (right whale) or "
            "≥100 yd (other large whales)."
        )

    if interaction_type == "strike":
        parts.append("Ship strike reported — notify NOAA immediately (1-866-755-6622).")
    elif interaction_type == "entanglement":
        parts.append(
            "Entanglement reported — contact NOAA Entanglement "
            "Hotline (1-866-755-6622). Do NOT attempt to "
            "disentangle."
        )
    elif interaction_type == "near_miss":
        parts.append(
            "Near-miss event — reduce speed to ≤10 knots and post a dedicated lookout."
        )
    elif interaction_type == "vessel_approach":
        parts.append(
            "Vessel approaching whale — slow to ≤10 knots, avoid abrupt course changes."
        )

    if risk_category in ("critical", "high"):
        parts.append(
            "This area has elevated collision risk. "
            "Voluntary speed reduction to ≤10 knots is "
            "strongly recommended."
        )

    return {
        "level": level,
        "message": " ".join(parts),
    }


# ── Main orchestrator ───────────────────────────────────────


def process_sighting_report(
    *,
    species_guess: str | None = None,
    description: str | None = None,
    interaction_type: str | None = None,
    lat: float | None = None,
    lon: float | None = None,
    image_bytes: bytes | None = None,
    image_filename: str | None = None,
    audio_bytes: bytes | None = None,
    audio_filename: str | None = None,
) -> dict[str, Any]:
    """Process a sighting report with optional photo + audio.

    Orchestrates:
    1. Photo classification (if image provided)
    2. Audio classification (if audio provided)
    3. Species assessment (reconcile user guess vs models)
    4. H3 risk lookup
    5. Advisory generation

    Returns a flat dict matching SightingReportResponse fields.
    """
    photo_result: dict[str, Any] | None = None
    audio_result: dict[str, Any] | None = None
    resolved_lat = lat
    resolved_lon = lon
    gps_source: str | None = "user" if lat is not None else None

    # ── 1. Photo classification ─────────────────────────────
    if image_bytes:
        photo_result = photo_svc.classify_photo(
            image_bytes=image_bytes,
            filename=image_filename or "upload.jpg",
            lat=lat,
            lon=lon,
        )
        # If user didn't provide coords, photo may have EXIF GPS
        if resolved_lat is None and photo_result.get("gps_source") == "exif":
            rc = photo_result.get("risk_context", {})
            resolved_lat = rc.get("cell_lat")
            resolved_lon = rc.get("cell_lon")
            gps_source = "exif"

    # ── 2. Audio classification ─────────────────────────────
    if audio_bytes and resolved_lat is not None and resolved_lon is not None:
        audio_result = audio_svc.classify_audio(
            audio_bytes=audio_bytes,
            filename=audio_filename or "upload.wav",
            lat=resolved_lat,
            lon=resolved_lon,
        )

    # ── 3. Resolve H3 cell + risk ───────────────────────────
    h3_cell: int | None = None
    risk_data: dict[str, Any] | None = None

    if resolved_lat is not None and resolved_lon is not None:
        h3_cell = _coords_to_h3(resolved_lat, resolved_lon)
        try:
            risk_data = get_cell_risk(h3_cell)
        except Exception:
            log.warning("Risk lookup failed for h3_cell=%s", h3_cell, exc_info=True)

    # ── 4. Species assessment ───────────────────────────────
    assessment = _build_species_assessment(
        species_guess=species_guess,
        photo_result=photo_result,
        audio_result=audio_result,
    )

    # ── 5. Advisory ─────────────────────────────────────────
    advisory_species = assessment.get("model_species") if assessment else None
    risk_category = risk_data.get("risk_category") if risk_data else None
    advisory = _generate_advisory(advisory_species, risk_category, interaction_type)

    # ── 6. Assemble response dict ───────────────────────────
    response: dict[str, Any] = {
        "user_input": {
            "species_guess": species_guess,
            "description": description,
            "interaction_type": interaction_type,
        },
    }

    # Location
    if resolved_lat is not None and resolved_lon is not None:
        response["location"] = {
            "lat": resolved_lat,
            "lon": resolved_lon,
            "h3_cell": h3_cell,
            "gps_source": gps_source,
        }

    # Photo
    if photo_result:
        response["photo_classification"] = {
            "predicted_species": photo_result["predicted_species"],
            "confidence": photo_result["confidence"],
            "probabilities": photo_result.get("probabilities", {}),
        }

    # Audio
    if audio_result:
        segments = audio_result.get("segments", [])
        response["audio_classification"] = {
            "dominant_species": audio_result["dominant_species"],
            "n_segments": audio_result["n_segments"],
            "segment_details": [
                {
                    "segment_idx": s.get("segment_idx", i),
                    "start_sec": s.get("start_sec", 0.0),
                    "end_sec": s.get("end_sec", 0.0),
                    "predicted_species": s.get("predicted_species", "unknown"),
                    "confidence": s.get("confidence", 0.0),
                }
                for i, s in enumerate(segments)
            ],
        }

    # Species assessment
    if assessment:
        response["species_assessment"] = assessment

    # Risk
    if risk_data:
        response["risk_summary"] = {
            "h3_cell": risk_data["h3_cell"],
            "risk_score": risk_data.get("risk_score"),
            "risk_category": risk_data.get("risk_category"),
            "traffic_score": risk_data.get("traffic_score"),
            "cetacean_score": risk_data.get("cetacean_score"),
            "proximity_score": risk_data.get("proximity_score"),
            "strike_score": risk_data.get("strike_score"),
            "habitat_score": risk_data.get("habitat_score"),
            "protection_gap": risk_data.get("protection_gap"),
            "reference_risk_score": risk_data.get("reference_risk_score"),
        }

    # Advisory
    response["advisory"] = advisory

    return response


# ── Species assessment logic ────────────────────────────────


def _build_species_assessment(
    *,
    species_guess: str | None,
    photo_result: dict[str, Any] | None,
    audio_result: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Reconcile user guess with model predictions.

    Priority: photo+audio consensus > photo > audio > user guess.
    """
    photo_species: str | None = None
    photo_conf: float = 0.0
    audio_species: str | None = None
    audio_conf: float = 0.0

    if photo_result:
        photo_species = _normalise_species(photo_result["predicted_species"])
        photo_conf = photo_result.get("confidence", 0.0)

    if audio_result:
        audio_species = _normalise_species(audio_result["dominant_species"])
        # Use max segment confidence for the dominant species
        segs = audio_result.get("segments", [])
        dominant = audio_result["dominant_species"]
        confs = [
            s.get("confidence", 0.0)
            for s in segs
            if s.get("predicted_species") == dominant
        ]
        audio_conf = max(confs) if confs else 0.0

    # Determine best prediction
    if photo_species and audio_species:
        # Both available — pick higher confidence, note if they agree
        if photo_species == audio_species:
            model_species = photo_species
            model_conf = max(photo_conf, audio_conf)
            source = "photo+audio"
        elif photo_conf >= audio_conf:
            model_species = photo_species
            model_conf = photo_conf
            source = "photo"
        else:
            model_species = audio_species
            model_conf = audio_conf
            source = "audio"
    elif photo_species:
        model_species = photo_species
        model_conf = photo_conf
        source = "photo"
    elif audio_species:
        model_species = audio_species
        model_conf = audio_conf
        source = "audio"
    elif species_guess:
        return {
            "model_species": _normalise_species(species_guess),
            "model_confidence": 0.0,
            "source": "user_only",
            "user_agrees": None,
        }
    else:
        return None

    # Compare with user guess
    user_agrees: bool | None = None
    if species_guess:
        user_agrees = _normalise_species(species_guess) == model_species

    return {
        "model_species": model_species,
        "model_confidence": round(model_conf, 4),
        "source": source,
        "user_agrees": user_agrees,
    }
