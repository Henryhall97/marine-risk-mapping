#!/usr/bin/env python3
"""Generate the expanded species_crosswalk.csv with global coverage + AphiaIDs.

Uses the expansion JSON from expand_crosswalk.py plus manually resolved
AphiaIDs for the 6 taxa that WoRMS exact-name lookup missed.
"""

import csv
import json
from pathlib import Path

CROSSWALK = Path("transform/seeds/species_crosswalk.csv")
EXPANSION = Path("scripts/crosswalk_expansion.json")
OUTPUT = Path("transform/seeds/species_crosswalk.csv")

# 6 taxa that WoRMS exact-name search missed (resolved in previous session)
MANUAL_APHIA = {
    "Balaenoptera musculus": 137090,
    "Lagenorhynchus": 137020,
    "Stenella": 137024,
    "Mesoplodon densirostris": 137122,
    "Mesoplodon bidens": 137121,
    "Mesoplodon ginkgodens": 231407,
}

# Common names for the 39 new species + new families/genera
COMMON_NAMES = {
    # Balaenopteridae
    "Balaenoptera bonaerensis": "Antarctic minke whale",
    "Balaenoptera omurai": "Omura's whale",
    "Balaenoptera ricei": "Rice's whale",
    # Delphinidae
    "Cephalorhynchus commersonii": "Commerson's dolphin",
    "Cephalorhynchus eutropia": "Chilean dolphin",
    "Cephalorhynchus hectori": "Hector's dolphin",
    "Lagenorhynchus obscurus": "Dusky dolphin",
    "Lissodelphis peronii": "Southern right whale dolphin",
    "Orcaella brevirostris": "Irrawaddy dolphin",
    "Orcaella heinsohni": "Australian snubfin dolphin",
    "Sotalia fluviatilis": "Tucuxi",
    "Sousa chinensis": "Indo-Pacific humpback dolphin",
    "Sousa sahulensis": "Australian humpback dolphin",
    "Sousa teuszii": "Atlantic humpback dolphin",
    "Tursiops aduncus": "Indo-Pacific bottlenose dolphin",
    "Tursiops australis": "Burrunan dolphin",
    "Tursiops erebennus": "Tamanend's bottlenose dolphin",
    # Iniidae
    "Inia araguaiaensis": "Araguaian river dolphin",
    "Inia boliviensis": "Bolivian river dolphin",
    # Monodontidae
    "Monodon monoceros": "Narwhal",
    # Neobalaenidae
    "Caperea marginata": "Pygmy right whale",
    # Phocoenidae
    "Neophocaena asiaeorientalis": "Yangtze finless porpoise",
    "Phocoena dioptrica": "Spectacled porpoise",
    "Phocoena spinipinnis": "Burmeister's porpoise",
    # Platanistidae
    "Platanista gangetica": "South Asian river dolphin",
    # Pontoporiidae
    "Pontoporia blainvillei": "Franciscana",
    # Ziphiidae
    "Berardius arnuxii": "Arnoux's beaked whale",
    "Berardius minimus": "Sato's beaked whale",
    "Hyperoodon planifrons": "Southern bottlenose whale",
    "Mesoplodon bowdoini": "Andrews' beaked whale",
    "Mesoplodon eueu": "Ramari's beaked whale",
    "Mesoplodon grayi": "Gray's beaked whale",
    "Mesoplodon hectori": "Hector's beaked whale",
    "Mesoplodon hotaula": "Deraniyagala's beaked whale",
    "Mesoplodon layardii": "Strap-toothed beaked whale",
    "Mesoplodon perrini": "Perrin's beaked whale",
    "Mesoplodon stejnegeri": "Stejneger's beaked whale",
    "Mesoplodon traversii": "Spade-toothed beaked whale",
    "Tasmacetus shepherdi": "Shepherd's beaked whale",
    # New genera (not species — for genus-level IDs)
    "Orcaella": "Orcaella (genus)",
    "Cephalorhynchus": "Cephalorhynchus (genus)",
    "Monodon": "Narwhal (genus)",
    "Caperea": "Pygmy right whale (genus)",
    "Platanista": "South Asian river dolphin (genus)",
    "Pontoporia": "Franciscana (genus)",
    "Tasmacetus": "Shepherd's beaked whale (genus)",
    "Berardius": "Beaked whale (genus)",
    "Inia": "River dolphin (genus)",
    "Sotalia": "Sotalia (genus)",
    "Sousa": "Humpback dolphin (genus)",
    "Neophocaena": "Finless porpoise (genus)",
    "Lissodelphis": "Right whale dolphin (genus)",
}

# Species groups for new taxa
SPECIES_GROUPS = {
    # Balaenopteridae new species
    "Balaenoptera bonaerensis": "minke_whale",
    "Balaenoptera omurai": "omuras_whale",
    "Balaenoptera ricei": "rices_whale",
    # Delphinidae new species
    "Cephalorhynchus commersonii": "other_dolphin",
    "Cephalorhynchus eutropia": "other_dolphin",
    "Cephalorhynchus hectori": "hectors_dolphin",
    "Lagenorhynchus obscurus": "other_dolphin",
    "Lissodelphis peronii": "other_dolphin",
    "Orcaella brevirostris": "other_dolphin",
    "Orcaella heinsohni": "other_dolphin",
    "Sotalia fluviatilis": "other_dolphin",
    "Sousa chinensis": "other_dolphin",
    "Sousa sahulensis": "other_dolphin",
    "Sousa teuszii": "other_dolphin",
    "Tursiops aduncus": "bottlenose_dolphin",
    "Tursiops australis": "bottlenose_dolphin",
    "Tursiops erebennus": "bottlenose_dolphin",
    # Iniidae
    "Inia araguaiaensis": "other_dolphin",
    "Inia boliviensis": "other_dolphin",
    # Monodontidae
    "Monodon monoceros": "narwhal",
    # Neobalaenidae
    "Caperea marginata": "pygmy_right_whale",
    # Phocoenidae
    "Neophocaena asiaeorientalis": "other_porpoise",
    "Phocoena dioptrica": "other_porpoise",
    "Phocoena spinipinnis": "other_porpoise",
    # Platanistidae
    "Platanista gangetica": "other_dolphin",
    # Pontoporiidae
    "Pontoporia blainvillei": "other_dolphin",
    # Ziphiidae
    "Berardius arnuxii": "beaked_whale",
    "Berardius minimus": "beaked_whale",
    "Hyperoodon planifrons": "beaked_whale",
    "Mesoplodon bowdoini": "beaked_whale",
    "Mesoplodon eueu": "beaked_whale",
    "Mesoplodon grayi": "beaked_whale",
    "Mesoplodon hectori": "beaked_whale",
    "Mesoplodon hotaula": "beaked_whale",
    "Mesoplodon layardii": "beaked_whale",
    "Mesoplodon perrini": "beaked_whale",
    "Mesoplodon stejnegeri": "beaked_whale",
    "Mesoplodon traversii": "beaked_whale",
    "Tasmacetus shepherdi": "beaked_whale",
}

# Conservation priority for new taxa
CONSERVATION = {
    "Balaenoptera ricei": "critical",  # ~50 individuals, Gulf of Mexico endemic
    # Maui dolphin subspecies critically endangered
    "Cephalorhynchus hectori": "critical",
    "Monodon monoceros": "moderate",
    "Caperea marginata": "moderate",
    "Balaenoptera bonaerensis": "moderate",
    "Balaenoptera omurai": "moderate",  # Data deficient, recently described
    "Orcaella brevirostris": "high",  # Vulnerable
    "Platanista gangetica": "high",  # Endangered
    "Pontoporia blainvillei": "high",  # Vulnerable
    "Sousa teuszii": "critical",  # Critically endangered
    # Yangtze subspecies critically endangered
    "Neophocaena asiaeorientalis": "critical",
    "Phocoena spinipinnis": "moderate",
    "Berardius minimus": "moderate",  # Recently described
}

# Family lookups
FAMILY_MAP = {
    "Balaenidae": {"is_baleen": True},
    "Balaenopteridae": {"is_baleen": True},
    "Eschrichtiidae": {"is_baleen": True},
    "Neobalaenidae": {"is_baleen": True},
    "Delphinidae": {"is_baleen": False},
    "Phocoenidae": {"is_baleen": False},
    "Physeteridae": {"is_baleen": False},
    "Kogiidae": {"is_baleen": False},
    "Ziphiidae": {"is_baleen": False},
    "Monodontidae": {"is_baleen": False},
    "Platanistidae": {"is_baleen": False},
    "Pontoporiidae": {"is_baleen": False},
    "Iniidae": {"is_baleen": False},
    "Lipotidae": {"is_baleen": False},
}

# New family-level rows
NEW_FAMILIES = {
    "Balaenidae": (136978, "Right whale (family)", "unid_baleen", True, "high"),
    "Eschrichtiidae": (136981, "Gray whale (family)", "gray_whale", True, "moderate"),
    "Neobalaenidae": (
        231385,
        "Pygmy right whale (family)",
        "pygmy_right_whale",
        True,
        "moderate",
    ),
    "Physeteridae": (136985, "Sperm whale (family)", "sperm_whale", False, "high"),
    "Kogiidae": (
        136982,
        "Small sperm whale (family)",
        "small_sperm_whale",
        False,
        "low",
    ),
    "Monodontidae": (136983, "Monodontidae (family)", "narwhal", False, "moderate"),
    "Platanistidae": (
        254965,
        "River dolphin (family)",
        "other_dolphin",
        False,
        "moderate",
    ),
    "Pontoporiidae": (342635, "Franciscana (family)", "other_dolphin", False, "high"),
    "Iniidae": (254958, "River dolphin (family)", "other_dolphin", False, "moderate"),
}

# New genus-level rows we should add
NEW_GENERA = {
    "Orcaella": (343985, "Delphinidae", "other_dolphin", False, "moderate"),
    "Cephalorhynchus": (231403, "Delphinidae", "other_dolphin", False, "moderate"),
    "Monodon": (137030, "Monodontidae", "narwhal", False, "moderate"),
    "Caperea": (231384, "Neobalaenidae", "pygmy_right_whale", True, "moderate"),
    "Platanista": (254966, "Platanistidae", "other_dolphin", False, "moderate"),
    "Pontoporia": (254963, "Pontoporiidae", "other_dolphin", False, "high"),
    "Tasmacetus": (137036, "Ziphiidae", "beaked_whale", False, "low"),
    "Berardius": (137032, "Ziphiidae", "beaked_whale", False, "low"),
    "Sotalia": (137025, "Delphinidae", "other_dolphin", False, "low"),
    "Sousa": (137023, "Delphinidae", "other_dolphin", False, "low"),
    "Neophocaena": (254984, "Phocoenidae", "other_porpoise", False, "moderate"),
    "Lissodelphis": (137019, "Delphinidae", "other_dolphin", False, "low"),
    "Inia": (254959, "Iniidae", "other_dolphin", False, "moderate"),
}


def main():
    with open(EXPANSION) as f:
        data = json.load(f)

    existing_aphia = data["existing_aphia_ids"]
    existing_aphia.update(MANUAL_APHIA)
    missing_species = data["missing_species"]

    # Build a complete AphiaID lookup: expansion JSON + manual + new taxa
    all_aphia = dict(existing_aphia)
    for name, info in missing_species.items():
        all_aphia[name] = info["aphia_id"]
    for fam, (aid, *_) in NEW_FAMILIES.items():
        all_aphia[fam] = aid
    for gen, (aid, *_) in NEW_GENERA.items():
        all_aphia[gen] = aid

    # Read existing CSV
    rows = []
    with open(CROSSWALK) as f:
        reader = csv.DictReader(f)
        base_fields = [
            c for c in reader.fieldnames if c not in ("aphia_id", "worms_lsid")
        ]
        fieldnames = base_fields + ["aphia_id", "worms_lsid"]
        for row in reader:
            name = row["scientific_name"]
            # Prefer lookup; fall back to existing value in CSV
            aid = all_aphia.get(name) or row.get("aphia_id") or ""
            if isinstance(aid, str) and aid.strip() == "":
                aid = ""
            row["aphia_id"] = aid
            row["worms_lsid"] = (
                f"urn:lsid:marinespecies.org:taxname:{aid}" if aid else ""
            )
            rows.append(row)

    # Add new family-level rows
    for fam_name, (aid, common, group, is_baleen, priority) in NEW_FAMILIES.items():
        # Check not already in crosswalk
        if fam_name not in {r["scientific_name"] for r in rows}:
            rows.append(
                {
                    "scientific_name": fam_name,
                    "common_name": common,
                    "species_group": group,
                    "nisi_species": "",
                    "strike_species": "",
                    "taxonomic_rank": "family",
                    "family": fam_name,
                    "is_baleen": str(is_baleen).lower(),
                    "conservation_priority": priority,
                    "aphia_id": aid,
                    "worms_lsid": f"urn:lsid:marinespecies.org:taxname:{aid}",
                }
            )

    # Add new genus-level rows
    for genus_name, (aid, family, group, is_baleen, priority) in NEW_GENERA.items():
        if genus_name not in {r["scientific_name"] for r in rows}:
            common = COMMON_NAMES.get(genus_name, f"{genus_name} (genus)")
            rows.append(
                {
                    "scientific_name": genus_name,
                    "common_name": common,
                    "species_group": group,
                    "nisi_species": "",
                    "strike_species": "",
                    "taxonomic_rank": "genus",
                    "family": family,
                    "is_baleen": str(is_baleen).lower(),
                    "conservation_priority": priority,
                    "aphia_id": aid,
                    "worms_lsid": f"urn:lsid:marinespecies.org:taxname:{aid}",
                }
            )

    # Add new species rows
    for name, info in sorted(missing_species.items()):
        if name in {r["scientific_name"] for r in rows}:
            continue
        family = info["family"]
        is_baleen = FAMILY_MAP.get(family, {}).get("is_baleen", False)
        common = COMMON_NAMES.get(name, name)
        group = SPECIES_GROUPS.get(name, "other_cetacean")
        priority = CONSERVATION.get(name, "low")

        rows.append(
            {
                "scientific_name": name,
                "common_name": common,
                "species_group": group,
                "nisi_species": "",
                "strike_species": "",
                "taxonomic_rank": "species",
                "family": family,
                "is_baleen": str(is_baleen).lower(),
                "conservation_priority": priority,
                "aphia_id": info["aphia_id"],
                "worms_lsid": f"urn:lsid:marinespecies.org:taxname:{info['aphia_id']}",
            }
        )

    # Sort: order (Cetacea), suborders (Mysticeti, Odontoceti),
    # then families alphabetically, then genera, then species
    RANK_ORDER = {"order": 0, "suborder": 1, "family": 2, "genus": 3, "species": 4}

    def sort_key(r):
        rank = RANK_ORDER.get(r.get("taxonomic_rank", "species"), 4)
        fam = r.get("family", "") or ""
        name = r.get("scientific_name", "")
        # Keep Cetacea/Mysticeti/Odontoceti at top
        if name in ("Cetacea", "Mysticeti", "Odontoceti"):
            return (0, name, "", "")
        return (1, fam, rank, name)

    rows.sort(key=sort_key)

    # Write output
    with open(OUTPUT, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} taxa to {OUTPUT}")

    # Summary stats
    ranks = {}
    for r in rows:
        rk = r.get("taxonomic_rank", "?")
        ranks[rk] = ranks.get(rk, 0) + 1
    print(f"By rank: {ranks}")

    has_aphia = sum(1 for r in rows if r.get("aphia_id"))
    print(f"With AphiaID: {has_aphia}/{len(rows)}")

    families = set(r.get("family", "") for r in rows if r.get("family"))
    print(f"Families represented: {sorted(families)}")


if __name__ == "__main__":
    main()
