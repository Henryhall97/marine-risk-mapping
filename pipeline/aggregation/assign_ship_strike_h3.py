"""Assign H3 cells to ship strike records.

Reads geocoded ship strikes from PostGIS, computes the H3
resolution-7 cell for each (lat, lon) using the shared
assign_h3_cells() utility, and writes the mapping back
to PostGIS as the ship_strike_h3 table.

Only strikes with non-null coordinates are assigned (67 of 261).

Run with:
    uv run python -m pipeline.aggregation.assign_ship_strike_h3
"""

import logging

from pipeline.utils import assign_h3_cells

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)


def main() -> None:
    """Assign ship strikes to H3 cells."""
    assign_h3_cells(
        source_table="ship_strikes",
        id_column="id",
        lat_column="latitude",
        lon_column="longitude",
        target_table="ship_strike_h3",
        fk_column="strike_id",
        fk_reference="ship_strikes(id)",
        index_name="idx_strike_h3_cell",
    )


if __name__ == "__main__":
    main()
