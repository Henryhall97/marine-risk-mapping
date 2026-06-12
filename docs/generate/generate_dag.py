"""
Generate a visual DAG diagram of the marine risk mapping dbt pipeline.
Shows all sources, seeds, staging, intermediate, and mart models with their dependencies.
"""

import graphviz

dot = graphviz.Digraph(
    "marine_risk_dag",
    format="png",
    engine="dot",
    graph_attr={
        "rankdir": "LR",
        "bgcolor": "#0d1117",
        "fontname": "Helvetica Neue",
        "pad": "0.5",
        "nodesep": "0.4",
        "ranksep": "1.8",
        "dpi": "150",
        "label": "Marine Risk Mapping — Data Pipeline DAG",
        "labelloc": "t",
        "fontsize": "28",
        "fontcolor": "#e6edf3",
    },
)

# ── Colour palette ──────────────────────────────────────────────
SRC_FILL = "#1f3a5f"  # deep navy  — raw source tables
SRC_FONT = "#8db8e8"
SEED_FILL = "#2d4a22"  # forest green — seeds
SEED_FONT = "#a3d977"
STG_FILL = "#3b2e5a"  # purple — staging views
STG_FONT = "#c4a8ff"
INT_FILL = "#4a3728"  # warm brown — intermediate tables
INT_FONT = "#f0c674"
MART_FILL = "#5c1a1a"  # deep red — mart tables
MART_FONT = "#ff7b72"
EDGE_COLOR = "#484f58"


# ── Node style helpers ──────────────────────────────────────────
def src_node(name, label=None):
    dot.node(
        name,
        label or name.replace("src_", ""),
        shape="cylinder",
        style="filled",
        fillcolor=SRC_FILL,
        fontcolor=SRC_FONT,
        fontsize="11",
        fontname="Helvetica Neue",
        color="#30506d",
        penwidth="1.5",
    )


def seed_node(name, label=None):
    dot.node(
        name,
        label or name,
        shape="note",
        style="filled",
        fillcolor=SEED_FILL,
        fontcolor=SEED_FONT,
        fontsize="11",
        fontname="Helvetica Neue Bold",
        color="#4a7a33",
        penwidth="1.5",
    )


def stg_node(name, label=None):
    dot.node(
        name,
        label or name,
        shape="box",
        style="filled,rounded",
        fillcolor=STG_FILL,
        fontcolor=STG_FONT,
        fontsize="11",
        fontname="Helvetica Neue",
        color="#5a4580",
        penwidth="1.5",
    )


def int_node(name, label=None):
    dot.node(
        name,
        label or name,
        shape="box",
        style="filled,rounded",
        fillcolor=INT_FILL,
        fontcolor=INT_FONT,
        fontsize="12",
        fontname="Helvetica Neue Bold",
        color="#6b5540",
        penwidth="1.5",
    )


def mart_node(name, label=None):
    dot.node(
        name,
        label or name,
        shape="doubleoctagon",
        style="filled",
        fillcolor=MART_FILL,
        fontcolor=MART_FONT,
        fontsize="13",
        fontname="Helvetica Neue Bold",
        color="#8b3030",
        penwidth="2",
    )


def edge(src, dst, **kw):
    dot.edge(
        src,
        dst,
        color=kw.get("color", EDGE_COLOR),
        penwidth=kw.get("penwidth", "1.2"),
        arrowsize="0.7",
        arrowhead="vee",
    )


# ── SOURCES (raw PostGIS tables) ───────────────────────────────
sources = [
    ("src_ais_h3_summary", "ais_h3_summary\n(9.7M rows)"),
    ("src_cetacean_sightings", "cetacean_sightings\n(364K rows)"),
    ("src_cetacean_sighting_h3", "cetacean_sighting_h3\n(76K cells)"),
    ("src_ship_strikes", "ship_strikes\n(261 records)"),
    ("src_ship_strike_h3", "ship_strike_h3\n(67 cells)"),
    ("src_bathymetry_h3", "bathymetry_h3\n(1M cells)"),
    ("src_cell_proximity", "cell_proximity\n(1.9M cells)"),
    ("src_ocean_covariates", "ocean_covariates\n(1.1M rows)"),
    ("src_nisi_risk_grid", "nisi_risk_grid\n(1.1M cells)"),
    ("src_marine_protected_areas", "marine_protected_areas"),
    ("src_rw_speed_zones", "right_whale_speed_zones\n(5 zones)"),
    ("src_sma", "seasonal_management_areas\n(10 zones)"),
]
for sid, slabel in sources:
    src_node(sid, slabel)

# ── SEED ────────────────────────────────────────────────────────
seed_node("species_crosswalk", "species_crosswalk\n(71 rows — CSV seed)")

# ── STAGING (views) ─────────────────────────────────────────────
staging = [
    "stg_cetacean_sightings",
    "stg_ship_strikes",
    "stg_marine_protected_areas",
    "stg_speed_zones",
    "stg_ocean_covariates",
    "stg_nisi_risk_grid",
]
for s in staging:
    stg_node(s)

# ── INTERMEDIATE (tables) ──────────────────────────────────────
intermediate = [
    ("int_hex_grid", "int_hex_grid\n(1.9M cells)"),
    ("int_vessel_traffic", "int_vessel_traffic\n(9.7M rows)"),
    ("int_cetacean_density", "int_cetacean_density\n(76K cells)"),
    ("int_ship_strike_density", "int_ship_strike_density\n(67 cells)"),
    ("int_bathymetry", "int_bathymetry\n(1M cells)"),
    ("int_proximity", "int_proximity\n(1.9M cells)\n4 distances + 4 decay scores"),
    ("int_mpa_coverage", "int_mpa_coverage\n(21K cells)"),
    ("int_speed_zone_coverage", "int_speed_zone_coverage\n(30K cells)"),
    ("int_ocean_covariates", "int_ocean_covariates\n(1.1M cells)"),
    ("int_nisi_reference_risk", "int_nisi_reference_risk\n(1.1M cells)"),
]
for iid, ilabel in intermediate:
    int_node(iid, ilabel)

# ── MARTS (tables) ─────────────────────────────────────────────
marts = [
    (
        "fct_collision_risk",
        "fct_collision_risk\n(1.8M cells)\n7 sub-scores → composite risk",
    ),
    (
        "fct_whale_sdm_training",
        "fct_whale_sdm_training\n(1.8M cells)\nSDM feature matrix",
    ),
    (
        "fct_strike_risk_training",
        "fct_strike_risk_training\n(1.8M cells)\nStrike model features",
    ),
    ("fct_species_risk", "fct_species_risk\n(98K rows)\nPer-species risk"),
    ("fct_monthly_traffic", "fct_monthly_traffic\n(9.2M rows)\nMonthly vessel stats"),
]
for mid, mlabel in marts:
    mart_node(mid, mlabel)

# ── EDGES: Source → Staging ─────────────────────────────────────
edge("src_cetacean_sightings", "stg_cetacean_sightings")
edge("src_ship_strikes", "stg_ship_strikes")
edge("species_crosswalk", "stg_ship_strikes", color="#4a7a33")
edge("src_marine_protected_areas", "stg_marine_protected_areas")
edge("src_rw_speed_zones", "stg_speed_zones")
edge("src_sma", "stg_speed_zones")
edge("src_ocean_covariates", "stg_ocean_covariates")
edge("src_nisi_risk_grid", "stg_nisi_risk_grid")

# ── EDGES: Source → Intermediate (direct source reads) ──────────
edge("src_ais_h3_summary", "int_hex_grid")
edge("src_cetacean_sighting_h3", "int_hex_grid")
edge("src_ship_strike_h3", "int_hex_grid")
edge("src_ais_h3_summary", "int_vessel_traffic")
edge("src_cetacean_sighting_h3", "int_cetacean_density")
edge("src_ship_strike_h3", "int_ship_strike_density")
edge("src_bathymetry_h3", "int_bathymetry")
edge("src_cell_proximity", "int_proximity")

# ── EDGES: Staging → Intermediate ──────────────────────────────
edge("stg_cetacean_sightings", "int_cetacean_density")
edge("stg_ship_strikes", "int_ship_strike_density")
edge("stg_marine_protected_areas", "int_mpa_coverage")
edge("stg_speed_zones", "int_speed_zone_coverage")
edge("stg_ocean_covariates", "int_ocean_covariates")
edge("stg_nisi_risk_grid", "int_nisi_reference_risk")

# ── EDGES: Intermediate ↔ Intermediate (hex_grid joins) ────────
for target in [
    "int_mpa_coverage",
    "int_speed_zone_coverage",
    "int_ocean_covariates",
    "int_nisi_reference_risk",
]:
    edge("int_hex_grid", target, color="#6b5540")

# ── EDGES: Intermediate → Marts ────────────────────────────────
# fct_collision_risk (joins ALL 10 intermediate models)
collision_deps = [
    "int_hex_grid",
    "int_vessel_traffic",
    "int_cetacean_density",
    "int_ship_strike_density",
    "int_bathymetry",
    "int_proximity",
    "int_mpa_coverage",
    "int_speed_zone_coverage",
    "int_ocean_covariates",
    "int_nisi_reference_risk",
]
for dep in collision_deps:
    edge(dep, "fct_collision_risk", color="#8b3030", penwidth="1.8")

# fct_whale_sdm_training
sdm_deps = [
    "int_hex_grid",
    "int_cetacean_density",
    "int_vessel_traffic",
    "int_bathymetry",
    "int_ocean_covariates",
    "int_proximity",
    "int_speed_zone_coverage",
    "int_mpa_coverage",
    "int_nisi_reference_risk",
]
for dep in sdm_deps:
    edge(dep, "fct_whale_sdm_training")

# fct_strike_risk_training
strike_deps = [
    "int_hex_grid",
    "int_vessel_traffic",
    "int_ship_strike_density",
    "int_cetacean_density",
    "int_bathymetry",
    "int_ocean_covariates",
    "int_proximity",
    "int_speed_zone_coverage",
    "int_mpa_coverage",
    "int_nisi_reference_risk",
]
for dep in strike_deps:
    edge(dep, "fct_strike_risk_training")

# fct_species_risk (has staging + seed + source + intermediate deps)
edge("src_cetacean_sighting_h3", "fct_species_risk")
edge("stg_cetacean_sightings", "fct_species_risk")
edge("species_crosswalk", "fct_species_risk", color="#4a7a33")
for dep in [
    "int_hex_grid",
    "int_vessel_traffic",
    "int_ship_strike_density",
    "int_speed_zone_coverage",
    "int_mpa_coverage",
    "int_bathymetry",
    "int_ocean_covariates",
    "int_nisi_reference_risk",
]:
    edge(dep, "fct_species_risk")

# fct_monthly_traffic
for dep in [
    "int_vessel_traffic",
    "int_bathymetry",
    "int_cetacean_density",
    "int_mpa_coverage",
]:
    edge(dep, "fct_monthly_traffic")

# ── LEGEND ──────────────────────────────────────────────────────
with dot.subgraph(name="cluster_legend") as lg:
    lg.attr(
        label="Legend",
        fontsize="16",
        fontcolor="#e6edf3",
        style="dashed",
        color="#484f58",
        bgcolor="#161b22",
    )
    lg.node(
        "leg_src",
        "Source Table\n(raw PostGIS)",
        shape="cylinder",
        style="filled",
        fillcolor=SRC_FILL,
        fontcolor=SRC_FONT,
        fontsize="10",
        fontname="Helvetica Neue",
        color="#30506d",
    )
    lg.node(
        "leg_seed",
        "CSV Seed",
        shape="note",
        style="filled",
        fillcolor=SEED_FILL,
        fontcolor=SEED_FONT,
        fontsize="10",
        fontname="Helvetica Neue",
        color="#4a7a33",
    )
    lg.node(
        "leg_stg",
        "Staging View",
        shape="box",
        style="filled,rounded",
        fillcolor=STG_FILL,
        fontcolor=STG_FONT,
        fontsize="10",
        fontname="Helvetica Neue",
        color="#5a4580",
    )
    lg.node(
        "leg_int",
        "Intermediate Table",
        shape="box",
        style="filled,rounded",
        fillcolor=INT_FILL,
        fontcolor=INT_FONT,
        fontsize="10",
        fontname="Helvetica Neue",
        color="#6b5540",
    )
    lg.node(
        "leg_mart",
        "Mart Table",
        shape="doubleoctagon",
        style="filled",
        fillcolor=MART_FILL,
        fontcolor=MART_FONT,
        fontsize="10",
        fontname="Helvetica Neue",
        color="#8b3030",
    )
    lg.edge("leg_src", "leg_seed", style="invis")
    lg.edge("leg_seed", "leg_stg", style="invis")
    lg.edge("leg_stg", "leg_int", style="invis")
    lg.edge("leg_int", "leg_mart", style="invis")

# ── RANK HINTS (keep layers aligned) ───────────────────────────
with dot.subgraph() as s:
    s.attr(rank="same")
    for sid, _ in sources:
        s.node(sid)

with dot.subgraph() as s:
    s.attr(rank="same")
    for st in staging:
        s.node(st)
    s.node("species_crosswalk")

with dot.subgraph() as s:
    s.attr(rank="same")
    for iid, _ in intermediate:
        s.node(iid)

with dot.subgraph() as s:
    s.attr(rank="same")
    for mid, _ in marts:
        s.node(mid)

# ── RENDER ──────────────────────────────────────────────────────
output_path = dot.render(
    filename="marine_risk_dag",
    directory="/Users/henryhall/Code/marine_risk_mapping/docs",
    cleanup=True,
)
print(f"✅ DAG diagram saved to: {output_path}")
