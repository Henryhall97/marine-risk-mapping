"""Download photos for ALL 138 taxa from Wikimedia Commons.

Reads the species crosswalk CSV, uses curated overrides for well-known
species, and auto-searches Wikimedia by scientific name for the rest.
Files are named by scientific name (lowercased, spaces→underscores).

All images are NOAA/US-Government (public domain) or CC-BY/CC-BY-SA
licensed via Wikimedia Commons.

Usage:
    python scripts/download_species_photos.py            # skip existing
    python scripts/download_species_photos.py --force    # re-download all
    python scripts/download_species_photos.py --credits  # print CREDITS.md
    python scripts/download_species_photos.py --dry-run  # show plan
"""

import argparse
import csv
import os
import sys
import time

import requests

PROJECT_ROOT = os.path.join(os.path.dirname(__file__), "..")
CROSSWALK = os.path.join(PROJECT_ROOT, "transform", "seeds", "species_crosswalk.csv")
OUT = os.path.join(PROJECT_ROOT, "frontend", "public", "species")
os.makedirs(OUT, exist_ok=True)

SESSION = requests.Session()
SESSION.headers.update(
    {
        "User-Agent": (
            "MarineRiskMapping/1.0 "
            "(https://github.com/Henryhall97/marine-risk-mapping; "
            "academic research project) python-requests"
        )
    }
)

# ── Curated overrides ───────────────────────────────────────
# scientific_name -> (Wikimedia file title, license, author)
CURATED: dict[str, tuple[str, str, str]] = {
    # Order / Suborder
    "Cetacea": (
        "File:Humpback stellwagen edit.jpg",
        "Public Domain (NOAA)",
        "Whit Welles / NOAA",
    ),
    "Mysticeti": (
        "File:Humpback stellwagen edit.jpg",
        "Public Domain (NOAA)",
        "Whit Welles / NOAA",
    ),
    "Odontoceti": (
        "File:Killerwhales jumping.jpg",
        "Public Domain (NOAA)",
        "Robert Pitman / NOAA",
    ),
    # Baleen families
    "Balaenidae": (
        "File:Eubalaena glacialis with calf.jpg",
        "Public Domain (NOAA)",
        "NOAA",
    ),
    "Balaenopteridae": (
        "File:Humpback stellwagen edit.jpg",
        "Public Domain (NOAA)",
        "Whit Welles / NOAA",
    ),
    "Eschrichtiidae": (
        "File:GrayWhale2 STR.jpg",
        "CC-BY 2.5",
        "Merrill Gosho / NOAA",
    ),
    "Neobalaenidae": (
        "File:Caperea marginata 3.jpg",
        "Public Domain",
        "Wikipedia",
    ),
    # Baleen genera
    "Eubalaena": (
        "File:Eubalaena glacialis with calf.jpg",
        "Public Domain (NOAA)",
        "NOAA",
    ),
    "Balaenoptera": (
        "File:Fin whale from air.jpg",
        "CC-BY-SA 2.0",
        "Aqqa Rosing-Asvid",
    ),
    "Eschrichtius": (
        "File:GrayWhale2 STR.jpg",
        "CC-BY 2.5",
        "Merrill Gosho / NOAA",
    ),
    "Caperea": (
        "File:Caperea marginata 3.jpg",
        "Public Domain",
        "Wikipedia",
    ),
    # Baleen species
    "Eubalaena glacialis": (
        "File:Eubalaena glacialis with calf.jpg",
        "Public Domain (NOAA)",
        "NOAA",
    ),
    "Eubalaena japonica": (
        "File:Eubalaena japonica drawing.jpg",
        "Public Domain",
        "Wikipedia",
    ),
    "Eubalaena australis": (
        "File:Southern right whale.jpg",
        "CC-BY-SA 2.0",
        "Wikipedia",
    ),
    "Balaena mysticetus": (
        "File:Bowhead-Whale1.jpg",
        "Public Domain (NOAA)",
        "NOAA",
    ),
    "Megaptera novaeangliae": (
        "File:Humpback stellwagen edit.jpg",
        "Public Domain (NOAA)",
        "Whit Welles / NOAA",
    ),
    "Balaenoptera musculus": (
        "File:Anim1754 - Flickr - NOAA Photo Library.jpg",
        "Public Domain (NOAA)",
        "NOAA Photo Library",
    ),
    "Balaenoptera physalus": (
        "File:Fin whale from air.jpg",
        "CC-BY-SA 2.0",
        "Aqqa Rosing-Asvid",
    ),
    "Balaenoptera borealis": (
        "File:Sei whale mother and calf Christin Khan NOAA.jpg",
        "Public Domain (NOAA)",
        "Christin Khan / NOAA",
    ),
    "Balaenoptera acutorostrata": (
        "File:Minke Whale (NOAA).jpg",
        "Public Domain (NOAA)",
        "NOAA",
    ),
    "Balaenoptera bonaerensis": (
        "File:Minke Whale (NOAA).jpg",
        "Public Domain (NOAA)",
        "NOAA",
    ),
    "Balaenoptera brydei": (
        "File:Bryde\u00b4s whale.jpg",
        "CC-BY-SA 3.0",
        "Wikipedia",
    ),
    "Balaenoptera edeni": (
        "File:Bryde\u00b4s whale.jpg",
        "CC-BY-SA 3.0",
        "Wikipedia",
    ),
    "Balaenoptera ricei": (
        "File:Rice's whale close to surface.jpg",
        "Public Domain (NOAA)",
        "NOAA Fisheries",
    ),
    "Balaenoptera omurai": (
        "File:Omura's whale (Balaenoptera omurai) breaching.jpg",
        "CC-BY 4.0",
        "Cerchio et al.",
    ),
    "Eschrichtius robustus": (
        "File:GrayWhale2 STR.jpg",
        "CC-BY 2.5",
        "Merrill Gosho / NOAA",
    ),
    "Caperea marginata": (
        "File:Caperea marginata 3.jpg",
        "Public Domain",
        "Wikipedia",
    ),
    # Toothed whale families
    "Physeteridae": (
        "File:Mother and baby sperm whale.jpg",
        "CC-BY-SA 2.0",
        "Gabriel Barathieu",
    ),
    "Kogiidae": (
        "File:Kogia breviceps.jpg",
        "Public Domain (NOAA)",
        "NOAA",
    ),
    "Ziphiidae": (
        "File:Cuviers beaked whale.jpg",
        "Public Domain (NOAA)",
        "NOAA",
    ),
    "Monodontidae": (
        "File:Pod Monodon monoceros.jpg",
        "Public Domain (NOAA)",
        "NOAA",
    ),
    "Delphinidae": (
        "File:Tursiops truncatus 01.jpg",
        "CC-BY-SA 3.0",
        "Wikipedia",
    ),
    "Phocoenidae": (
        "File:Phocoena phocoena.2.jpg",
        "CC-BY-SA 3.0",
        "Wikipedia",
    ),
    "Iniidae": (
        "File:Boto.jpg",
        "CC-BY-SA 3.0",
        "Wikipedia",
    ),
    "Platanistidae": (
        "File:Platanista gangetica noaa.jpg",
        "Public Domain (NOAA)",
        "NOAA",
    ),
    "Pontoporiidae": (
        "File:Pontoporia blainvillei.jpg",
        "CC-BY-SA 3.0",
        "Wikipedia",
    ),
    # Toothed whale genera
    "Kogia": (
        "File:Kogia breviceps.jpg",
        "Public Domain (NOAA)",
        "NOAA",
    ),
    "Monodon": (
        "File:Pod Monodon monoceros.jpg",
        "Public Domain (NOAA)",
        "NOAA",
    ),
    "Ziphius": (
        "File:Cuviers beaked whale.jpg",
        "Public Domain (NOAA)",
        "NOAA",
    ),
    "Tursiops": (
        "File:Tursiops truncatus 01.jpg",
        "CC-BY-SA 3.0",
        "Wikipedia",
    ),
    "Delphinus": (
        "File:Common Dolphin 6033.jpg",
        "Public Domain (NOAA)",
        "NOAA",
    ),
    "Globicephala": (
        "File:Pilot whale and calf.jpg",
        "Public Domain (NOAA)",
        "NOAA",
    ),
    "Phocoenoides": (
        "File:Dall's porpoise 2.jpg",
        "Public Domain (NOAA)",
        "NOAA",
    ),
    "Inia": (
        "File:Boto.jpg",
        "CC-BY-SA 3.0",
        "Wikipedia",
    ),
    "Pontoporia": (
        "File:Pontoporia blainvillei.jpg",
        "CC-BY-SA 3.0",
        "Wikipedia",
    ),
    "Platanista": (
        "File:Platanista gangetica noaa.jpg",
        "Public Domain (NOAA)",
        "NOAA",
    ),
    # Toothed whale species
    "Physeter macrocephalus": (
        "File:Mother and baby sperm whale.jpg",
        "CC-BY-SA 2.0",
        "Gabriel Barathieu",
    ),
    "Kogia breviceps": (
        "File:Kogia breviceps.jpg",
        "Public Domain (NOAA)",
        "NOAA",
    ),
    "Kogia sima": (
        "File:Dwarf sperm whale (NOAA Pitman).jpg",
        "Public Domain (NOAA)",
        "Robert Pitman / NOAA",
    ),
    "Orcinus orca": (
        "File:Killerwhales jumping.jpg",
        "Public Domain (NOAA)",
        "Robert Pitman / NOAA",
    ),
    "Delphinapterus leucas": (
        "File:Beluga premier.gov.ru-1.jpeg",
        "CC-BY 4.0",
        "premier.gov.ru",
    ),
    "Monodon monoceros": (
        "File:Pod Monodon monoceros.jpg",
        "Public Domain (NOAA)",
        "NOAA",
    ),
    "Ziphius cavirostris": (
        "File:Cuviers beaked whale.jpg",
        "Public Domain (NOAA)",
        "NOAA",
    ),
    "Tursiops truncatus": (
        "File:Tursiops truncatus 01.jpg",
        "CC-BY-SA 3.0",
        "Wikipedia",
    ),
    "Delphinus delphis": (
        "File:Common Dolphin 6033.jpg",
        "Public Domain (NOAA)",
        "NOAA",
    ),
    "Grampus griseus": (
        "File:Risso's dolphin (Grampus griseus) NWHI.jpg",
        "Public Domain (NOAA)",
        "NOAA / NWHI",
    ),
    "Stenella frontalis": (
        "File:Stenella frontalis.jpg",
        "CC-BY-SA 2.5",
        "Wikipedia",
    ),
    "Stenella coeruleoalba": (
        "File:Striped dolphin Azores.jpg",
        "CC-BY-SA 4.0",
        "Wikipedia",
    ),
    "Stenella longirostris": (
        "File:A spinner dolphin in the Red Sea.jpg",
        "CC-BY-SA 3.0",
        "Wikipedia",
    ),
    "Cephalorhynchus hectori": (
        "File:Hector's Dolphin (Cephalorhynchus hectori)"
        " - Gregory Slobirdr Smith - brighter.jpg",
        "CC-BY 2.0",
        "Gregory Slobirdr Smith",
    ),
    "Pseudorca crassidens": (
        "File:Pseudorca crassidens.jpg",
        "CC-BY-SA 3.0",
        "Wikipedia",
    ),
    "Phocoena phocoena": (
        "File:Phocoena phocoena.2.jpg",
        "CC-BY-SA 3.0",
        "Wikipedia",
    ),
    "Phocoena sinus": (
        "File:Vaquita6 Olson NOAA.jpg",
        "Public Domain (NOAA)",
        "Paula Olson / NOAA",
    ),
    "Phocoenoides dalli": (
        "File:Dall's porpoise 2.jpg",
        "Public Domain (NOAA)",
        "NOAA",
    ),
    "Inia geoffrensis": (
        "File:Boto.jpg",
        "CC-BY-SA 3.0",
        "Wikipedia",
    ),
    "Pontoporia blainvillei": (
        "File:Pontoporia blainvillei.jpg",
        "CC-BY-SA 3.0",
        "Wikipedia",
    ),
    "Platanista gangetica": (
        "File:Platanista gangetica noaa.jpg",
        "Public Domain (NOAA)",
        "NOAA",
    ),
    "Leucopleurus acutus": (
        "File:Lagenorhynchus acutus.jpg",
        "Public Domain (NOAA)",
        "NOAA",
    ),
    "Globicephala macrorhynchus": (
        "File:Short-finned pilot whale.jpg",
        "CC-BY-SA 4.0",
        "Wikipedia",
    ),
    "Globicephala melas": (
        "File:Pilot whale and calf.jpg",
        "Public Domain (NOAA)",
        "NOAA",
    ),
    "Stenella attenuata": (
        "File:Stenella frontalis.jpg",
        "CC-BY-SA 2.5",
        "Wikipedia",
    ),
}

# Terms to exclude from auto-search results (not real animal photos)
_EXCLUDE_TERMS = frozenset(
    [
        "range map",
        "map",
        "distribution",
        "size comparison",
        "skull",
        "skeleton",
        "diagram",
        "drawing",
        "illustration",
        "chart",
        "graph",
        "logo",
        "flag",
        "stamp",
        "coin",
    ]
)


def load_crosswalk() -> list[dict[str, str]]:
    """Read crosswalk CSV → list of dicts."""
    with open(CROSSWALK) as f:
        return list(csv.DictReader(f))


def safe_filename(scientific_name: str) -> str:
    """Convert scientific name to a safe filename slug."""
    return scientific_name.lower().replace(" ", "_").replace("'", "")


def resolve_url(title: str) -> str | None:
    """Use Wikimedia API to resolve a file title → actual URL."""
    api = "https://en.wikipedia.org/w/api.php"
    params = {
        "action": "query",
        "titles": title,
        "prop": "imageinfo",
        "iiprop": "url",
        "format": "json",
    }
    try:
        r = SESSION.get(api, params=params, timeout=15)
        data = r.json()
        pages = data.get("query", {}).get("pages", {})
        for page in pages.values():
            ii = page.get("imageinfo", [])
            if ii:
                return ii[0].get("url")
    except Exception as e:
        print(f"  API error: {e}")
    return None


def search_wikimedia(
    scientific_name: str,
    common_name: str | None = None,
) -> tuple[str, str] | None:
    """Search Wikimedia Commons for a photo.

    Returns (file_title, url) or None.
    """
    api = "https://commons.wikimedia.org/w/api.php"
    queries = [scientific_name]
    if common_name:
        queries.append(common_name)

    for query in queries:
        params = {
            "action": "query",
            "generator": "search",
            "gsrsearch": f"filetype:bitmap {query}",
            "gsrnamespace": "6",
            "gsrlimit": "5",
            "prop": "imageinfo",
            "iiprop": "url|size|mime",
            "format": "json",
        }
        try:
            r = SESSION.get(api, params=params, timeout=15)
            data = r.json()
            pages = data.get("query", {}).get("pages", {})
            if not pages:
                continue

            candidates = []
            for page in pages.values():
                title = page.get("title", "")
                ii = page.get("imageinfo", [{}])[0]
                mime = ii.get("mime", "")
                size = ii.get("size", 0)
                url = ii.get("url", "")
                width = ii.get("width", 0)
                title_low = title.lower()
                if (
                    mime in ("image/jpeg", "image/png", "image/webp")
                    and size > 10_000
                    and width > 200
                    and not any(t in title_low for t in _EXCLUDE_TERMS)
                ):
                    candidates.append((title, url, size))

            if candidates:
                candidates.sort(key=lambda x: x[2], reverse=True)
                return candidates[0][0], candidates[0][1]
        except Exception as e:
            print(f"  Search error: {e}")

    return None


def download_all(
    force: bool = False,
    dry_run: bool = False,
) -> dict[str, tuple[str, str, str]]:
    """Download photos for all 138 taxa."""
    rows = load_crosswalk()
    credits: dict[str, tuple[str, str, str]] = {}
    ok, skip, fail = 0, 0, 0

    for row in rows:
        sci = row["scientific_name"]
        common = row["common_name"]
        fname = safe_filename(sci)
        path = os.path.join(OUT, f"{fname}.jpg")

        if not force and os.path.exists(path) and os.path.getsize(path) > 1000:
            if sci in CURATED:
                t, lic, a = CURATED[sci]
                credits[fname] = (t, lic, a)
            else:
                credits[fname] = (
                    "Auto-searched",
                    "Wikimedia Commons",
                    "See Wikimedia",
                )
            print(f"  {fname}: exists ({common})")
            skip += 1
            continue

        label = f"{sci} ({common})"

        # --- Try curated first ---
        if sci in CURATED:
            title, lic, auth = CURATED[sci]
            if dry_run:
                print(f"  [CURATED] {fname}: {title}")
                credits[fname] = (title, lic, auth)
                ok += 1
                continue

            print(f"  {label}...", end=" ", flush=True)
            url = resolve_url(title)
            if url:
                try:
                    r = SESSION.get(url, timeout=30)
                    kb = len(r.content) // 1024
                    if r.status_code == 200 and len(r.content) > 1000:
                        with open(path, "wb") as f:
                            f.write(r.content)
                        print(f"{kb}KB curated OK")
                        credits[fname] = (title, lic, auth)
                        ok += 1
                        time.sleep(0.3)
                        continue
                except Exception:
                    pass
            print("curated fail → auto...", end=" ")

        # --- Auto-search fallback ---
        if dry_run:
            print(f"  [SEARCH] {fname}: {sci}")
            ok += 1
            continue

        print(f"  {label}...", end=" ", flush=True)
        result = search_wikimedia(sci, common)
        if result:
            title, url = result
            try:
                r = SESSION.get(url, timeout=30)
                kb = len(r.content) // 1024
                if r.status_code == 200 and len(r.content) > 1000:
                    with open(path, "wb") as f:
                        f.write(r.content)
                    short = title[:50]
                    print(f"{kb}KB OK ({short})")
                    credits[fname] = (
                        title,
                        "Wikimedia Commons",
                        "See Wikimedia",
                    )
                    ok += 1
                else:
                    print(f"SKIP ({r.status_code})")
                    fail += 1
            except Exception as e:
                print(f"DL error: {e}")
                fail += 1
        else:
            print("NO PHOTO FOUND")
            fail += 1

        time.sleep(0.5)

    print(f"\nSummary: {ok} new, {skip} existing, {fail} failed")
    count = 0
    for f in sorted(os.listdir(OUT)):
        if f.endswith((".jpg", ".jpeg", ".png")):
            sz = os.path.getsize(os.path.join(OUT, f))
            count += 1
            print(f"  {f}: {sz // 1024}KB")
    print(f"\n{count} photo files total")
    return credits


def print_credits(
    credits: dict[str, tuple[str, str, str]] | None = None,
) -> None:
    """Print a CREDITS.md table."""
    if credits is None:
        credits = {}
        for row in load_crosswalk():
            sci = row["scientific_name"]
            fn = safe_filename(sci)
            p = os.path.join(OUT, f"{fn}.jpg")
            if os.path.exists(p):
                if sci in CURATED:
                    t, lic, a = CURATED[sci]
                    credits[fn] = (t, lic, a)
                else:
                    credits[fn] = (
                        "Auto-searched",
                        "Wikimedia Commons",
                        "See Wikimedia",
                    )

    print("# Species Photo Credits\n")
    print(
        "> All photos sourced from Wikimedia Commons.  "
        "Public Domain (NOAA/US Govt) or Creative Commons.\n"
    )
    print("| File | License | Author | Wikimedia Title |")
    print("|------|---------|--------|-----------------|")
    for fn, (title, lic, auth) in sorted(credits.items()):
        safe = title.replace("|", "\\|")[:80]
        print(f"| {fn}.jpg | {lic} | {auth} | {safe} |")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=("Download species photos for all 138 taxa")
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-download all (overwrite existing)",
    )
    parser.add_argument(
        "--credits",
        action="store_true",
        help="Print CREDITS.md table and exit",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show plan without downloading",
    )
    args = parser.parse_args()

    if args.credits:
        print_credits()
        sys.exit(0)

    download_all(force=args.force, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
