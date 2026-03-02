"""Assign H3 cells to cetacean sightings.

Reads cetacean sightings from PostGIS, computes the H3
resolution-7 cell for each (lat, lon) using the shared
assign_h3_cells() utility, and writes the mapping back
to PostGIS as the cetacean_sighting_h3 table.

Run with:
    uv run python -m pipeline.aggregation.assign_cetacean_h3
"""

import logging

from pipeline.utils import assign_h3_cells

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)


def main() -> None:
    """Assign cetacean sightings to H3 cells."""
    assign_h3_cells(
        source_table="cetacean_sightings",
        id_column="id",
        lat_column="decimal_latitude",
        lon_column="decimal_longitude",
        target_table="cetacean_sighting_h3",
        fk_column="sighting_id",
        fk_reference="cetacean_sightings(id)",
        index_name="idx_cetacean_h3_cell",
    )


if __name__ == "__main__":
    main()
