"""Final download pass for remaining species photos."""

import os

import requests

OUT = os.path.join(os.path.dirname(__file__), "..", "frontend", "public", "species")
S = requests.Session()
S.headers["User-Agent"] = "MarineRiskMapping/1.0 python-requests"
API = "https://commons.wikimedia.org/w/api.php"

# These are verified to exist on Commons
FIXES = {
    "common_dolphin": [
        "File:Common Dolphin 1.jpg",
        "File:Delphinus capensis.jpg",
        "File:Common dolphin.jpg",
    ],
    "pilot_whale": [
        "File:Short-finned pilot whale.jpg",
        "File:Globicephala macrorhynchus 01.jpg",
        "File:Pilot whales in the Strait of Gibraltar.jpg",
    ],
    "beaked_whale": [
        "File:Cuviers beaked whale 01.jpg",
        "File:Blainville's beaked whale.jpg",
        "File:Mesoplodon densirostris.jpg",
    ],
    "bowhead": [
        "File:Bowhead Whale NOAA.jpg",
        "File:A bowhead whale.jpg",
        "File:Balaena mysticetus NOAA.jpg",
    ],
}


def try_download(title):
    params = {
        "action": "query",
        "titles": title,
        "prop": "imageinfo",
        "iiprop": "url",
        "format": "json",
    }
    r = S.get(API, params=params, timeout=15)
    pages = r.json().get("query", {}).get("pages", {})
    for page in pages.values():
        ii = page.get("imageinfo", [])
        if ii:
            url = ii[0]["url"]
            img = S.get(url, timeout=30)
            if img.status_code == 200 and len(img.content) > 10000:
                return img.content
    return None


def main():
    for name, titles in FIXES.items():
        path = os.path.join(OUT, f"{name}.jpg")
        # Skip if already good (> 50KB)
        if os.path.exists(path) and os.path.getsize(path) > 50000:
            sz = os.path.getsize(path) // 1024
            print(f"  {name}: already good ({sz}KB)")
            continue

        # Remove tiny/bad file
        if os.path.exists(path):
            os.remove(path)

        print(f"\n{name}:")
        for title in titles:
            print(f"  Trying: {title} ...", end=" ")
            data = try_download(title)
            if data:
                with open(path, "wb") as f:
                    f.write(data)
                print(f"OK ({len(data) // 1024}KB)")
                break
            else:
                print("NOPE")
        else:
            print(f"  ALL FAILED for {name}")

    # Also search for any that still failed
    for name in FIXES:
        path = os.path.join(OUT, f"{name}.jpg")
        if os.path.exists(path) and os.path.getsize(path) > 10000:
            continue
        # Search fallback
        query = name.replace("_", " ")
        print(f"\n  Searching commons for '{query} photo'")
        params = {
            "action": "query",
            "list": "search",
            "srnamespace": "6",
            "srsearch": f"{query} photo",
            "srlimit": "5",
            "format": "json",
        }
        r = S.get(API, params=params, timeout=15)
        results = r.json().get("query", {}).get("search", [])
        for res in results:
            t = res.get("title", "")
            if t.lower().endswith((".jpg", ".jpeg", ".png")):
                print(f"  Trying search result: {t} ...", end=" ")
                data = try_download(t)
                if data:
                    with open(path, "wb") as f:
                        f.write(data)
                    print(f"OK ({len(data) // 1024}KB)")
                    break
                else:
                    print("NOPE")

    print("\nFinal:")
    for f in sorted(os.listdir(OUT)):
        if f.endswith((".jpg", ".jpeg")):
            sz = os.path.getsize(os.path.join(OUT, f))
            status = "OK" if sz > 50000 else "SMALL" if sz > 10000 else "TINY"
            print(f"  {f}: {sz // 1024}KB [{status}]")


if __name__ == "__main__":
    main()
