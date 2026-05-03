"""Fetch WoRMS AphiaIDs for all species in the crosswalk."""

import csv
import json
import time
import urllib.request

CROSSWALK = "transform/seeds/species_crosswalk.csv"

# WoRMS REST API base
BASE = "https://www.marinespecies.org/rest"


def fetch_aphia_id(name: str) -> int | None:
    """Look up AphiaID for a scientific name via WoRMS REST API."""
    encoded = name.replace(" ", "%20")
    url = f"{BASE}/AphiaIDByName/{encoded}?marine_only=true"
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = resp.read().decode()
            aid = json.loads(data)
            if isinstance(aid, int) and aid > 0:
                return aid
            return None
    except Exception as e:
        print(f"  ERROR for {name}: {e}")
        return None


def main() -> None:
    with open(CROSSWALK) as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    print(f"Looking up {len(rows)} taxa from WoRMS...")
    results = {}
    for row in rows:
        name = row["scientific_name"]
        if name in results:
            continue
        aid = fetch_aphia_id(name)
        results[name] = aid
        status = aid if aid else "NOT FOUND"
        print(f"  {name}: {status}")
        time.sleep(0.3)  # rate-limit

    print("\n--- Results ---")
    found = sum(1 for v in results.values() if v)
    print(f"Found: {found}/{len(results)}")
    missing = [k for k, v in results.items() if not v]
    if missing:
        print(f"Missing: {missing}")

    # Print CSV-ready output
    print("\n--- CSV mapping ---")
    for name, aid in results.items():
        lsid = f"urn:lsid:marinespecies.org:taxname:{aid}" if aid else ""
        print(f"{name},{aid or ''},{lsid}")


if __name__ == "__main__":
    main()
