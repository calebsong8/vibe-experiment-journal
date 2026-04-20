"""
Download bird call audio clips from Wikimedia Commons.
Uses aggressive rate-limiting to respect the CDN's request limits.
Stores up to MAX_CLIPS MP3/OGG files per bird under audio/birds/<slug>/.
"""

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

BIRDS = [
    "American Robin",
    "Northern Cardinal",
    "Blue Jay",
    "Red-tailed Hawk",
    "Mourning Dove",
    "Black-capped Chickadee",
    "American Crow",
    "Common Loon",
    "Mallard",
    "Bald Eagle",
    "Canada Goose",
    "Great Blue Heron",
    "Ruby-throated Hummingbird",
    "Tufted Titmouse",
    "White-breasted Nuthatch",
    "Carolina Wren",
    "European Starling",
    "House Sparrow",
    "House Finch",
    "American Goldfinch",
    "Song Sparrow",
    "Dark-eyed Junco",
    "Red-winged Blackbird",
    "Brown-headed Cowbird",
    "Common Grackle",
]

MAX_CLIPS = 2  # 2 clips/bird keeps total size manageable
MAX_FILE_KB = 6000  # raised to catch nuthatch/finch clips that were previously skipped
DOWNLOAD_DELAY = 4.0  # seconds between file downloads
BETWEEN_BIRDS = 2.0  # seconds between birds
RETRY_DELAYS = [8, 20, 45]  # backoff on 429

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "audio", "birds")
HEADERS = {"User-Agent": "BirdSynthApp/1.0 (educational; non-commercial)"}

SCIENTIFIC = {
    "American Robin": "Turdus migratorius",
    "Northern Cardinal": "Cardinalis cardinalis",
    "Blue Jay": "Cyanocitta cristata",
    "Red-tailed Hawk": "Buteo jamaicensis",
    "Mourning Dove": "Zenaida macroura",
    "Black-capped Chickadee": "Poecile atricapillus",
    "American Crow": "Corvus brachyrhynchos",
    "Common Loon": "Gavia immer",
    "Mallard": "Anas platyrhynchos",
    "Bald Eagle": "Haliaeetus leucocephalus",
    "Canada Goose": "Branta canadensis",
    "Great Blue Heron": "Ardea herodias",
    "Ruby-throated Hummingbird": "Archilochus colubris",
    "Tufted Titmouse": "Baeolophus bicolor",
    "White-breasted Nuthatch": "Sitta carolinensis",
    "Carolina Wren": "Thryothorus ludovicianus",
    "European Starling": "Sturnus vulgaris",
    "House Sparrow": "Passer domesticus",
    "House Finch": "Haemorhous mexicanus",
    "American Goldfinch": "Spinus tristis",
    "Song Sparrow": "Melospiza melodia",
    "Dark-eyed Junco": "Junco hyemalis",
    "Red-winged Blackbird": "Agelaius phoeniceus",
    "Brown-headed Cowbird": "Molothrus ater",
    "Common Grackle": "Quiscalus quiscula",
}


def slug(name: str) -> str:
    return name.lower().replace(" ", "_").replace("-", "_")


def fetch_json(url: str) -> Any:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def download_with_retry(url: str, dest: str) -> int:
    """Download url → dest with exponential backoff on 429. Returns bytes written."""
    for attempt, wait in enumerate([0] + RETRY_DELAYS):
        if wait:
            print(f"    rate-limited, waiting {wait}s...")
            time.sleep(wait)
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=90) as resp:
                with open(dest, "wb") as f:
                    total = 0
                    while True:
                        chunk = resp.read(32768)
                        if not chunk:
                            break
                        f.write(chunk)
                        total += len(chunk)
            return total
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < len(RETRY_DELAYS):
                continue
            raise
    raise RuntimeError("Max retries exceeded")


def wikimedia_search(query: str, limit: int = 8) -> list[dict[str, Any]]:
    encoded = urllib.parse.quote(query)
    url = (
        "https://commons.wikimedia.org/w/api.php"
        "?action=query&generator=search"
        f"&gsrsearch={encoded}"
        "&gsrnamespace=6"
        "&prop=imageinfo"
        "&iiprop=url|mime|size"
        f"&gsrlimit={limit}"
        "&format=json"
    )
    try:
        data = fetch_json(url)
        results: list[dict[str, Any]] = []
        for page in data.get("query", {}).get("pages", {}).values():
            ii = page.get("imageinfo", [{}])[0]
            mime = ii.get("mime", "")
            if "audio" not in mime and "ogg" not in mime:
                continue
            results.append(
                {
                    "title": page.get("title", ""),
                    "url": ii.get("url", ""),
                    "size": ii.get("size", 0),
                    "mime": mime,
                }
            )
        # prefer MP3, then sort by size ascending
        results.sort(key=lambda r: (0 if "mpeg" in r["mime"] else 1, r["size"]))
        return results
    except Exception as exc:
        print(f"    search error: {exc}")
        return []


def xeno_canto_search(name: str) -> list[dict[str, Any]]:
    """Fallback source: xeno-canto public API (no auth required)."""
    sci = SCIENTIFIC.get(name, name)
    encoded = urllib.parse.quote(f"{sci} type:call q:A")
    url = f"https://www.xeno-canto.org/api/2/recordings?query={encoded}"
    try:
        data = fetch_json(url)
        results: list[dict[str, Any]] = []
        for rec in data.get("recordings", []):
            file_url = rec.get("file", "")
            if not file_url:
                continue
            if file_url.startswith("//"):
                file_url = "https:" + file_url
            results.append(
                {
                    "title": rec.get("en", name),
                    "url": file_url,
                    "size": 0,  # unknown until download
                    "mime": "audio/mpeg",
                }
            )
        print(f"    xeno-canto: {len(results)} result(s) for {name}")
        return results[:MAX_CLIPS * 4]
    except Exception as exc:
        print(f"    xeno-canto search error: {exc}")
        return []


def find_candidates(name: str) -> list[dict[str, Any]]:
    sci = SCIENTIFIC.get(name, "")
    seen_urls: set[str] = set()
    candidates: list[dict[str, Any]] = []
    for query in [f"{sci} call", f"{name} bird call", f"{name} call", sci, name]:
        if not query or len(candidates) >= MAX_CLIPS * 4:
            continue
        for rec in wikimedia_search(query, limit=8):
            if rec["url"] and rec["url"] not in seen_urls:
                seen_urls.add(rec["url"])
                candidates.append(rec)
        time.sleep(1.0)  # polite API pacing
    return candidates


def download_bird(name: str) -> int:
    bird_dir = os.path.join(OUTPUT_DIR, slug(name))
    os.makedirs(bird_dir, exist_ok=True)

    existing = sorted(f for f in os.listdir(bird_dir) if f.endswith((".mp3", ".ogg")))
    if len(existing) >= MAX_CLIPS:
        print(f"  Already have {len(existing)} clip(s) — skipping")
        return len(existing)

    wiki_candidates = find_candidates(name)
    if not wiki_candidates:
        print("  Nothing on Wikimedia — trying xeno-canto...")
    xc_candidates = xeno_canto_search(name) if len(wiki_candidates) < MAX_CLIPS * 2 else []
    # xeno-canto results go after Wikimedia so Wikimedia is tried first
    candidates = wiki_candidates + [r for r in xc_candidates if r["url"] not in {c["url"] for c in wiki_candidates}]

    if not candidates:
        print("  No audio found on any source")
        return 0

    downloaded = len(existing)
    for rec in candidates[downloaded:]:
        if downloaded >= MAX_CLIPS:
            break
        size_kb = rec["size"] // 1024
        if size_kb > MAX_FILE_KB:
            print(f"  Skipping ({size_kb}KB > {MAX_FILE_KB}KB limit)")
            continue

        ext = ".ogg" if "ogg" in rec["mime"] else ".mp3"
        dest = os.path.join(bird_dir, f"{downloaded + 1}{ext}")
        try:
            written = download_with_retry(rec["url"], dest)
            print(f"  Clip {downloaded + 1}: {written // 1024}KB  {rec['title'][:55]}")
            downloaded += 1
            time.sleep(DOWNLOAD_DELAY)
        except Exception as exc:
            print(f"  Clip {downloaded + 1}: FAILED — {exc}")
            if os.path.exists(dest):
                os.remove(dest)

    return downloaded


def main() -> None:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print(f"Output: {OUTPUT_DIR}")
    print(
        f"Max {MAX_CLIPS} clips/bird, max {MAX_FILE_KB}KB/file, {DOWNLOAD_DELAY}s between downloads\n"
    )

    total_clips = 0
    birds_with_audio = 0

    for idx, name in enumerate(BIRDS, 1):
        print(f"[{idx:2d}/{len(BIRDS)}] {name}")
        count = download_bird(name)
        total_clips += count
        if count > 0:
            birds_with_audio += 1
        time.sleep(BETWEEN_BIRDS)

    total_bytes = sum(
        os.path.getsize(os.path.join(root, f))
        for root, _, files in os.walk(OUTPUT_DIR)
        for f in files
    )

    print(f"\n{'=' * 50}")
    print(f"Done.  {birds_with_audio}/{len(BIRDS)} birds with audio")
    print(f"       {total_clips} total clips")
    print(f"       {total_bytes / (1024 * 1024):.1f} MB total")


if __name__ == "__main__":
    main()
