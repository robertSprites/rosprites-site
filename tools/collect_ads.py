"""Collect distinct, locally hosted promotional artwork for the static ad wall."""

from concurrent.futures import ThreadPoolExecutor, as_completed
from hashlib import sha256
from html.parser import HTMLParser
from pathlib import Path
import json
import re
import struct
import threading
import time
import urllib.error
import urllib.parse
import urllib.request


ROOT = Path(__file__).resolve().parents[1]
DESTINATION = ROOT / "assets" / "ads"
DATA = ROOT / "data"
HEADERS = {"User-Agent": "Mozilla/5.0", "Accept-Language": "en-US,en;q=0.9"}
SEXUAL_TAGS = {12095, 6650, 9130, 24904}
EXCLUDE_TITLE = re.compile(
    r"\b(hentai|porn|erotic|sex|sexual|nsfw|nude|nudity|lewd|fetish|futanari|milf|waifu|succubus)\b",
    re.IGNORECASE,
)
request_lock = threading.Lock()
next_request = 0.0


def fetch(url, retries=2):
    global next_request
    for attempt in range(retries + 1):
        with request_lock:
            now = time.monotonic()
            wait = max(0.0, next_request - now)
            next_request = max(now, next_request) + 0.04
        if wait:
            time.sleep(wait)
        try:
            request = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(request, timeout=18) as response:
                return response.read()
        except urllib.error.HTTPError as error:
            if error.code not in (429, 500, 502, 503, 504) or attempt == retries:
                raise
            if error.code == 429:
                retry_after = error.headers.get("Retry-After", "60")
                delay = max(60, int(retry_after) if retry_after.isdigit() else 60)
                with request_lock:
                    next_request = max(next_request, time.monotonic() + delay)
                print(f"Source requested a cooldown; waiting {delay} seconds", flush=True)
        except (OSError, TimeoutError):
            if attempt == retries:
                raise
        time.sleep(1.5 * (attempt + 1))


class Results(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.items = []
        self.current = None
        self.in_title = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "a" and "search_result_row" in attrs.get("class", ""):
            app_id = attrs.get("data-ds-appid", "")
            tags = set(json.loads(attrs.get("data-ds-tagids", "[]")))
            descriptors = set(json.loads(attrs.get("data-ds-descids", "[]")))
            if app_id.isdigit() and not tags & SEXUAL_TAGS and not descriptors & {1, 3, 4}:
                self.current = {"id": int(app_id), "title": "", "thumbnail": ""}
            else:
                self.current = None
        elif self.current is not None:
            if tag == "img" and not self.current["thumbnail"]:
                self.current["thumbnail"] = attrs.get("src", "")
            if tag == "span" and "title" in attrs.get("class", "").split():
                self.in_title = True

    def handle_data(self, text):
        if self.current is not None and self.in_title:
            self.current["title"] += text

    def handle_endtag(self, tag):
        if tag == "span":
            self.in_title = False
        if tag == "a" and self.current is not None:
            item = self.current
            item["title"] = item["title"].strip()
            if item["title"] and item["thumbnail"] and not EXCLUDE_TITLE.search(item["title"]):
                self.items.append(item)
            self.current = None


def catalog():
    cached = DATA / "ad-catalog.json"
    if cached.exists():
        return json.loads(cached.read_text(encoding="utf-8"))
    checkpoint = DATA / "ad-catalog-progress.json"
    # Search artwork is supplied by the game's publisher. Exclude sexual tags
    # and content descriptors before requesting or displaying their artwork.
    items = [{"id": 2333480, "title": "RAID: Shadow Legends", "thumbnail": ""}]
    seen = {2333480}
    start = 0
    total = 1
    if checkpoint.exists():
        progress = json.loads(checkpoint.read_text(encoding="utf-8"))
        items = progress["items"]
        seen = {item["id"] for item in items}
        start = progress["start"]
        total = progress["total"]
    while start < total:
        time.sleep(3.2)
        query = urllib.parse.urlencode({
            "start": start, "count": 100, "supportedlang": "english",
            "category1": 998, "filter": "topsellers", "infinite": 1,
            "excludetags": ",".join(map(str, sorted(SEXUAL_TAGS))),
        })
        result = json.loads(fetch("https://store.steampowered.com/search/results/?" + query))
        if not result.get("success"):
            raise RuntimeError("The source returned an unsuccessful catalog response")
        total = int(result["total_count"])
        parser = Results()
        parser.feed(result["results_html"])
        for item in parser.items:
            if item["id"] not in seen:
                seen.add(item["id"])
                items.append(item)
        if start % 500 == 0 or start + 100 >= total:
            print(f"Catalog: scanned {min(start + 100, total)}/{total}, accepted {len(items)}", flush=True)
        start += 100
        checkpoint.write_text(json.dumps({"start": start, "total": total, "items": items}, ensure_ascii=False), encoding="utf-8")
    cached.write_text(json.dumps(items, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if checkpoint.exists():
        checkpoint.unlink()
    return items


def jpeg_size(raw):
    if not raw.startswith(b"\xff\xd8"):
        raise ValueError("Not a JPEG image")
    offset = 2
    while offset < len(raw):
        if raw[offset] != 0xFF:
            offset += 1
            continue
        while offset < len(raw) and raw[offset] == 0xFF:
            offset += 1
        marker = raw[offset]
        offset += 1
        if marker in (0xD8, 0xD9) or 0xD0 <= marker <= 0xD7:
            continue
        length = struct.unpack_from(">H", raw, offset)[0]
        if marker in (0xC0, 0xC1, 0xC2):
            height, width = struct.unpack_from(">HH", raw, offset + 3)
            return width, height
        if length < 2:
            break
        offset += length
    raise ValueError("JPEG dimensions were not found")


def download(item):
    app_id = item["id"]
    image_path = DESTINATION / f"{app_id}.jpg"
    primary = f"https://shared.fastly.steamstatic.com/store_item_assets/steam/apps/{app_id}/header.jpg"
    source = primary
    if image_path.exists():
        raw = image_path.read_bytes()
    else:
        try:
            raw = fetch(primary)
        except urllib.error.HTTPError as error:
            if error.code != 404 or not item["thumbnail"]:
                raise
            source = item["thumbnail"]
            raw = fetch(source)
    width, height = jpeg_size(raw)
    if width < 200 or height < 70:
        raise ValueError("Artwork is too small")
    digest = sha256(raw).hexdigest()
    image_path.write_bytes(raw)
    return {
        "id": app_id, "title": item["title"],
        "image": f"assets/ads/{app_id}.jpg", "width": width, "height": height,
        "source": f"https://store.steampowered.com/app/{app_id}/",
        "artwork": source, "sha256": digest, "bytes": len(raw),
    }


def main():
    DESTINATION.mkdir(parents=True, exist_ok=True)
    DATA.mkdir(exist_ok=True)
    items = catalog()
    print(f"Downloading artwork for {len(items)} products", flush=True)
    downloaded = {}
    failures = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        tasks = {executor.submit(download, item): item for item in items}
        for index, task in enumerate(as_completed(tasks), 1):
            item = tasks[task]
            try:
                downloaded[item["id"]] = task.result()
            except Exception as error:
                failures.append({"id": item["id"], "title": item["title"], "error": str(error)})
            if index % 200 == 0 or index == len(tasks):
                print(f"Artwork: {index}/{len(tasks)}, saved {len(downloaded)}, unavailable {len(failures)}", flush=True)
    seen_hashes = set()
    ads = []
    for item in items:
        result = downloaded.get(item["id"])
        if not result:
            continue
        if result["sha256"] in seen_hashes:
            (ROOT / result["image"]).unlink()
            continue
        seen_hashes.add(result["sha256"])
        ads.append(result)
    (DATA / "ads.json").write_text(json.dumps(ads, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (DATA / "ad-unavailable.json").write_text(json.dumps(failures, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    total = sum(item["bytes"] for item in ads)
    print(f"Complete: {len(ads)} distinct images, {total / 1024 / 1024:.1f} MiB, {len(failures)} unavailable", flush=True)


if __name__ == "__main__":
    main()
