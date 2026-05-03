"""Download remaining species photos using Commons API."""

import os

import requests

OUT = os.path.join(os.path.dirname(__file__), "..", "frontend", "public", "species")
os.makedirs(OUT, exist_ok=True)

S = requests.Session()
S.headers["User-Agent"] = "MarineRiskMapping/1.0 python-requests"

COMMONS_API = "https://commons.wikimedia.org/w/api.php"

REMAINING = {
    "minke_whale": "File:Minke whale NOAA.jpg",
    "gray_whale": "File:Gray whale calf breaching.jpg",
    "bowhead": "File:Bowhead Whale2.jpg",
    "common_dolphin": "File:Common dolphin noaa.jpg",
    "pilot_whale": "File:Pilot Whale and calf.jpg",
    "beaked_whale": "File:Cuviers beaked whale.jpg",
    "rissos_dolphin": "File:Grampus griseus Azores.jpg",
    "striped_dolphin": "File:Stenella coeruleoalba Azores.jpg",
    "dalls_porpoise": "File:Phocoenoides dalli (Dall's porpoise).jpg",
}


def search_commons(query):
    """Search commons for an image matching a query string."""
    params = {
        "action": "query",
        "list": "search",
        "srnamespace": "6",
        "srsearch": query,
        "srlimit": "3",
        "format": "json",
    }
    r = S.get(COMMONS_API, params=params, timeout=15)
    results = r.json().get("query", {}).get("search", [])
    for res in results:
        title = res.get("title", "")
        if title.lower().endswith((".jpg", ".jpeg", ".png")):
            return title
    return None


def resolve_and_download(title):
    """Resolve a Commons file title to URL and download."""
    params = {
        "action": "query",
        "titles": title,
        "prop": "imageinfo",
        "iiprop": "url",
        "format": "json",
    }
    r = S.get(COMMONS_API, params=params, timeout=15)
    pages = r.json().get("query", {}).get("pages", {})
    for page in pages.values():
        ii = page.get("imageinfo", [])
        if ii:
            url = ii[0]["url"]
            img = S.get(url, timeout=30)
            if img.status_code == 200 and len(img.content) > 5000:
                return img.content
    return None


def main():
    for name, title in REMAINING.items():
        path = os.path.join(OUT, f"{name}.jpg")
        if os.path.exists(path) and os.path.getsize(path) > 5000:
            print(f"  {name}: already exists, skipping")
            continue

        print(f"\n{name}:")

        # Try the explicit title first
        print(f"  Trying: {title}")
        data = resolve_and_download(title)
        if data:
            with open(path, "wb") as f:
                f.write(data)
            print(f"  OK ({len(data) // 1024}KB)")
            continue

        # Fall back to search
        search_term = name.replace("_", " ")
        print(f"  Title failed. Searching: '{search_term}'")
        found = search_commons(search_term)
        if found:
            print(f"  Found: {found}")
            data = resolve_and_download(found)
            if data:
                with open(path, "wb") as f:
                    f.write(data)
                print(f"  OK ({len(data) // 1024}KB)")
                continue

        # Try broader search
        broad = search_term + " whale" if "whale" not in search_term else search_term
        if broad != search_term:
            print(f"  Trying broader: '{broad}'")
            found = search_commons(broad)
            if found:
                print(f"  Found: {found}")
                data = resolve_and_download(found)
                if data:
                    with open(path, "wb") as f:
                        f.write(data)
                    print(f"  OK ({len(data) // 1024}KB)")
                    continue

        print("  FAILED")

    print("\n\nFinal inventory:")
    for f in sorted(os.listdir(OUT)):
        if f.endswith(".jpg"):
            size = os.path.getsize(os.path.join(OUT, f))
            print(f"  {f}: {size // 1024}KB")


if __name__ == "__main__":
    main()
