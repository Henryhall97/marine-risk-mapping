"""
Generate a visual diagram of key/foreign key relationships in the marine_risk database.
"""

import graphviz

dot = graphviz.Digraph(
    "marine_risk_fk",
    format="png",
    engine="dot",
    graph_attr={
        "rankdir": "LR",
        "bgcolor": "#0d1117",
        "fontname": "Helvetica Neue",
        "pad": "0.5",
        "nodesep": "0.6",
        "ranksep": "1.8",
        "dpi": "150",
        "label": "Marine Risk Mapping — Key/Foreign Key Relationships",
        "labelloc": "t",
        "fontsize": "24",
        "fontcolor": "#e6edf3",
    },
)

# Node style
TABLE_FILL = "#1f3a5f"
TABLE_FONT = "#8db8e8"
FK_COLOR = "#ff7b72"

# Helper to add table nodes


def table_node(schema, table):
    dot.node(
        f"{schema}.{table}",
        f"{schema}.{table}",
        shape="box",
        style="filled,rounded",
        fillcolor=TABLE_FILL,
        fontcolor=TABLE_FONT,
        fontsize="13",
        fontname="Helvetica Neue Bold",
        color="#30506d",
        penwidth="2",
    )


# Add all tables
for schema, table in [
    ("topology", "layer"),
    ("topology", "topology"),
    ("public", "cetacean_sighting_h3"),
    ("public", "cetacean_sightings"),
    ("public", "ship_strike_h3"),
    ("public", "ship_strikes"),
]:
    table_node(schema, table)

# Add FK edges
fk_edges = [
    ("topology.layer", "topology.topology", "topology_id", "id"),
    ("public.cetacean_sighting_h3", "public.cetacean_sightings", "sighting_id", "id"),
    ("public.ship_strike_h3", "public.ship_strikes", "strike_id", "id"),
]
for src, dst, src_col, dst_col in fk_edges:
    dot.edge(
        src,
        dst,
        label=f"{src_col} → {dst_col}",
        color=FK_COLOR,
        fontcolor=FK_COLOR,
        penwidth="2.2",
        arrowsize="0.9",
        arrowhead="normal",
    )

# Render
output_path = dot.render(
    filename="marine_risk_fk_diagram",
    directory="/Users/henryhall/Code/marine_risk_mapping/docs/diagrams",
    cleanup=True,
)
print(f"✅ FK diagram saved to: {output_path}")
