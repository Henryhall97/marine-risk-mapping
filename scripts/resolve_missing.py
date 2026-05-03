"""Resolve the 7 missing AphiaIDs."""

import json
import time
import urllib.request

BASE = "https://www.marinespecies.org/rest"

missing = {
    "Balaenoptera musculus": "Balaenoptera+musculus",
    "Lagenorhynchus": "Lagenorhynchus",
    "Stenella": "Stenella",
    "Mesoplodon densirostris": "Mesoplodon+densirostris",
    "Mesoplodon bidens": "Mesoplodon+bidens",
    "Inia geoffrensis": "Inia+geoffrensis",
    "Mesoplodon ginkgodens": "Mesoplodon+ginkgodens",
}

for name, query in missing.items():
    url = f"{BASE}/AphiaRecordsByName/{query}?like=false&marine_only=false"
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
            if data:
                for rec in data[:3]:
                    print(
                        f"{name}: AphiaID={rec['AphiaID']}, "
                        f"status={rec['status']}, "
                        f"valid={rec.get('valid_name', '')}"
                    )
            else:
                print(f"{name}: no results")
    except Exception as e:
        print(f"{name}: ERROR {e}")
    time.sleep(0.5)
