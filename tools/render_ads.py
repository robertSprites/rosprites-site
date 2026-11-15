"""Render the local ad manifest as ordinary, lazy-loaded image elements."""

from html import escape
from pathlib import Path
import json
import re

ROOT = Path(__file__).resolve().parents[1]
ads = json.loads((ROOT / "data" / "ads.json").read_text(encoding="utf-8"))
if not ads:
    raise RuntimeError("There is no artwork to render")
lines = []
for ad in ads:
    if not (ROOT / ad["image"]).is_file():
        raise FileNotFoundError(ad["image"])
    lines.append(
        f'        <img src="{escape(ad["image"], quote=True)}" '
        f'width="{ad["width"]}" height="{ad["height"]}" '
        f'alt="{escape(ad["title"], quote=True)} promotional artwork" '
        'loading="lazy" decoding="async" fetchpriority="low">'
    )
path = ROOT / "index.html"
html = path.read_text(encoding="utf-8")
replacement = '<!-- ADS:START -->\n' + '\n'.join(lines) + '\n        <!-- ADS:END -->'
html, matches = re.subn(r'<!-- ADS:START -->[\s\S]*?<!-- ADS:END -->', lambda _: replacement, html)
if matches != 1:
    raise RuntimeError("Expected exactly one ad wall")
path.write_text(html, encoding="utf-8", newline="\n")
print(f"Rendered {len(ads):,} distinct, unlinked images.")
