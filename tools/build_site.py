"""Create a static publish folder from an explicit list, never from the collector."""
from pathlib import Path
import json
import shutil
from export_analytics import validate_public_snapshot

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_FILES = ["index.html", "preview.jpg", "assets/site.css", "assets/analytics.css", "assets/analytics.js", "data/ugc-stats.json"]


def build():
    output = ROOT / "dist"
    snapshot = ROOT / "data" / "ugc-stats.json"
    if not snapshot.is_file():
        raise SystemExit("Export analytics first: python tools/export_analytics.py --help")
    data = json.loads(snapshot.read_text(encoding="utf-8"))
    validate_public_snapshot(data)
    # Never copy a source directory recursively. Build only known public assets.
    # Refuse unexpected existing files instead of accidentally republishing them.
    if output.exists():
        unexpected = [p.relative_to(output).as_posix() for p in output.rglob("*")
                      if p.is_file() and p.relative_to(output).as_posix() not in PUBLIC_FILES]
        if unexpected:
            raise SystemExit("Unexpected files in dist; inspect it before rebuilding: " + ", ".join(unexpected))
    for relative in PUBLIC_FILES:
        source = ROOT / relative
        if source.is_symlink() or not source.is_file():
            raise SystemExit("Missing or linked public file: " + relative)
        destination = output / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
    print("Static site prepared in dist/. Publish only that folder.")


if __name__ == "__main__":
    build()
