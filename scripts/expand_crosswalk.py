#!/usr/bin/env python3
"""Expand species_crosswalk.csv to global cetacean coverage.

Fetches all accepted species from WoRMS under each cetacean family,
compares with the existing crosswalk, and outputs the missing taxa
with AphiaIDs. Also adds AphiaIDs to existing taxa.

WoRMS REST API: https://www.marinespecies.org/rest/
"""

import csv
import json
import time
from pathlib import Path
from urllib.parse import quote
from urllib.request import urlopen

CROSSWALK = Path("transform/seeds/species_crosswalk.csv")

# All accepted extant cetacean families from WoRMS
FAMILIES = {
    # Mysticeti
    "Balaenidae": 136978,
    "Balaenopteridae": 136979,
    "Eschrichtiidae": 136981,
    "Neobalaenidae": 231385,
    # Odontoceti
    "Delphinidae": 136980,
    "Phocoenidae": 136984,
    "Physeteridae": 136985,
    "Kogiidae": 136982,
    "Ziphiidae": 136986,
    "Monodontidae": 136983,
    "Platanistidae": 254965,
    "Pontoporiidae": 342635,
    "Iniidae": 254958,
    "Lipotidae": 254963,  # Yangtze river dolphin (likely extinct)
}

# Higher taxa AphiaIDs we want to keep
HIGHER_TAXA = {
    "Cetacea": 2688,
    "Mysticeti": 148724,
    "Odontoceti": 148723,
}


def fetch_json(url: str) -> list | dict:
    """Fetch JSON from a URL with rate limiting."""
    time.sleep(0.3)  # Be nice to WoRMS
    with urlopen(url) as resp:
        return json.loads(resp.read().decode())


def get_children(aphia_id: int, rank: str = "Species") -> list[dict]:
    """Get all accepted children of a taxon at a given rank."""
    base = "https://www.marinespecies.org/rest"
    results = []
    offset = 1
    while True:
        url = (
            f"{base}/AphiaChildrenByAphiaID/{aphia_id}"
            f"?marine_only=false&offset={offset}"
        )
        try:
            data = fetch_json(url)
        except Exception as e:
            print(f"  Error fetching offset {offset}: {e}")
            break
        if not data:
            break
        for item in data:
            if item.get("status") == "accepted" and item.get("rank") == rank:
                results.append(item)
        if len(data) < 50:
            break
        offset += 50
    return results


def get_genera(family_id: int) -> list[dict]:
    """Get accepted genera for a family."""
    return get_children(family_id, "Genus")


def get_species(genus_id: int) -> list[dict]:
    """Get accepted species under a genus."""
    return get_children(genus_id, "Species")


def get_aphia_id(name: str) -> int | None:
    """Look up a single AphiaID by exact name."""
    url = (
        "https://www.marinespecies.org/rest/AphiaIDByName/"
        f"{quote(name)}?marine_only=false"
    )
    try:
        result = fetch_json(url)
        return int(result) if result and int(result) > 0 else None
    except Exception:
        return None


def load_existing() -> dict[str, dict]:
    """Load existing crosswalk keyed by scientific_name."""
    rows = {}
    with open(CROSSWALK) as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows[row["scientific_name"]] = row
    return rows


def main():
    existing = load_existing()
    print(f"Existing crosswalk: {len(existing)} taxa\n")

    # Step 1: Collect all accepted species from WoRMS by family
    all_species: dict[str, dict] = {}  # name -> {aphia_id, family, ...}

    for family_name, family_id in FAMILIES.items():
        print(f"\n{'=' * 60}")
        print(f"Fetching genera for {family_name} ({family_id})...")
        genera = get_genera(family_id)
        print(f"  Found {len(genera)} accepted genera")

        for genus in genera:
            genus_name = genus["scientificname"]
            genus_id = genus["AphiaID"]
            print(f"  Genus: {genus_name} ({genus_id})")

            species = get_species(genus_id)
            print(f"    -> {len(species)} accepted species")

            for sp in species:
                name = sp["scientificname"]
                all_species[name] = {
                    "aphia_id": sp["AphiaID"],
                    "family": family_name,
                    "genus": genus_name,
                    "is_baleen": family_name
                    in (
                        "Balaenidae",
                        "Balaenopteridae",
                        "Eschrichtiidae",
                        "Neobalaenidae",
                    ),
                }

    print(f"\n{'=' * 60}")
    print(f"Total accepted species from WoRMS: {len(all_species)}")

    # Step 2: Find what's missing
    existing_names = set(existing.keys())
    worms_names = set(all_species.keys())

    # Species in WoRMS but not in our crosswalk
    missing = worms_names - existing_names
    # Species in our crosswalk that are higher ranks (genera, families, etc.)
    # These are fine — we keep them

    print(f"\nMissing from crosswalk: {len(missing)} species")
    print("\nMissing species by family:")

    by_family: dict[str, list] = {}
    for name in sorted(missing):
        info = all_species[name]
        fam = info["family"]
        by_family.setdefault(fam, []).append(name)

    for fam in sorted(by_family):
        print(f"\n  {fam}:")
        for name in by_family[fam]:
            info = all_species[name]
            print(f"    {name} (AphiaID: {info['aphia_id']})")

    # Step 3: Add AphiaIDs to existing taxa
    print(f"\n{'=' * 60}")
    print("Looking up AphiaIDs for existing taxa...")
    existing_aphia: dict[str, int | None] = {}
    for name in sorted(existing.keys()):
        aid = get_aphia_id(name)
        existing_aphia[name] = aid
        status = f"✓ {aid}" if aid else "✗ NOT FOUND"
        print(f"  {name}: {status}")

    # Step 4: Also get family-level AphiaIDs
    print(f"\n{'=' * 60}")
    print("Family-level AphiaIDs (for new families):")
    for fam, fid in FAMILIES.items():
        if fam not in existing_names:
            print(f"  {fam}: {fid}")

    # Save results to JSON for the next script to use
    output = {
        "existing_aphia_ids": {k: v for k, v in existing_aphia.items() if v},
        "missing_species": {name: all_species[name] for name in sorted(missing)},
        "families": FAMILIES,
        "higher_taxa": HIGHER_TAXA,
    }
    out_path = Path("scripts/crosswalk_expansion.json")
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nSaved expansion data to {out_path}")


if __name__ == "__main__":
    main()
