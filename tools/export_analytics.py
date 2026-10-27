"""Export explicitly selected public aggregates; never read Roblox credentials.

The source database stays outside the site and is opened in SQLite read-only mode.
No buyer IDs, transaction IDs, individual timestamps, or raw metadata are exported.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import sqlite3
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def utc_iso(value):
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    except (ValueError, TypeError):
        return None


def number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return value if math.isfinite(value) else None


def meta(db, key):
    row = db.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
    if not row:
        return None
    try:
        return json.loads(row[0])
    except (ValueError, TypeError):
        return None


def export_snapshot(db_path, *, group_id=None, group_name="My Roblox group",
                    revenue=False, financials=False, balance=False, now=None):
    path = Path(db_path).resolve()
    if not path.is_file():
        raise ValueError("Sales database not found. Sync your private analytics tool first.")
    revenue = revenue or financials
    now = now or datetime.now(timezone.utc)
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=15)) as db:
        db.execute("BEGIN")  # one consistent snapshot while the private collector syncs
        available = [row[0] for row in db.execute(
            "SELECT DISTINCT source FROM sales WHERE source LIKE 'group:%'")]
        if group_id is None:
            if len(available) != 1:
                raise ValueError("Use --group-id to select one group (no group or multiple groups found).")
            source = available[0]
            group_id = int(source.split(":")[1])
        else:
            source = f"group:{int(group_id)}"
        if source not in available:
            raise ValueError("Selected group has no synced sales. Check the group ID and sync first.")

        # Only group aggregates are selected. Personal sales are never included.
        money_sql = ", SUM(robux), COUNT(robux)" if revenue else ""
        rows = db.execute(
            "SELECT substr(created, 1, 10), asset_id, asset_name, location, COUNT(*)"
            + money_sql + " FROM sales WHERE source = ? "
            "GROUP BY substr(created, 1, 10), asset_id, asset_name, location "
            "ORDER BY substr(created, 1, 10)", (source,))
        items, buckets = {}, defaultdict(dict)
        for row in rows:
            day, asset_id, name, location, count = row[:5]
            try:
                parsed_day = datetime.strptime(day, "%Y-%m-%d").date()
            except (ValueError, TypeError):
                raise ValueError("A sale has an invalid date; export stopped without replacing the snapshot.") from None
            if parsed_day > now.date():
                raise ValueError("A sale is dated in the future; export stopped.")
            name = str(name or "Unnamed item")[:300]
            asset_id = int(asset_id) if asset_id and int(asset_id) > 0 else None
            key = f"asset-{asset_id}" if asset_id else "item-" + hashlib.sha256(name.encode()).hexdigest()[:16]
            items[key] = {"key": key, "assetId": asset_id, "name": name}
            bucket = buckets[day].setdefault(key, {
                "key": key, "sales": 0, "inGame": 0, "website": 0, "other": 0,
                **({"earnedRobux": 0} if revenue else {})})
            bucket["sales"] += count
            bucket[{"Game": "inGame", "Website": "website"}.get(location, "other")] += count
            if revenue:
                amount, known = row[5:7]
                if known != count or bucket["earnedRobux"] is None:
                    bucket["earnedRobux"] = None
                else:
                    bucket["earnedRobux"] += amount or 0

        watermark = db.execute("SELECT value FROM meta WHERE key = ?", (f"watermark:{source}",)).fetchone()
        catalog = meta(db, "catalog") or {}
        cat = catalog.get(source, {}) if isinstance(catalog, dict) else {}
        output = {
            "schemaVersion": 1,
            "generatedAt": now.isoformat().replace("+00:00", "Z"),
            "group": {"id": int(group_id), "name": str(group_name)[:200]},
            "coverage": {
                "firstRecordedDay": min(buckets, default=None),
                "lastRecordedDay": max(buckets, default=None),
                "syncedThrough": utc_iso(watermark[0]) if watermark else None,
            },
            "itemsOnSale": {"count": number(cat.get("items")), "asOf": number(cat.get("as_of"))},
            "includes": {"revenue": revenue, "financials": financials, "balance": balance},
            "items": sorted(items.values(), key=lambda item: item["key"]),
            "daily": [{"date": day, "items": sorted(entries.values(), key=lambda item: item["key"])}
                      for day, entries in sorted(buckets.items())],
        }
        if financials:
            raw = meta(db, "financials") or {}
            fin = raw.get(source, {}) if isinstance(raw, dict) else {}
            output["financials"] = {field: number(fin.get(field))
                                    for field in ("funds", "pending", "sales_month", "updated")}
        if balance:
            raw = meta(db, "balance") or {}
            output["accountBalance"] = {"robux": number(raw.get("robux")), "asOf": number(raw.get("ts"))}
    return output


def write_snapshot(snapshot, destination):
    validate_public_snapshot(snapshot)
    destination = Path(destination).resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Replace atomically: a failed export leaves the previous good file intact.
    fd, temporary = tempfile.mkstemp(prefix="ugc-export-", suffix=".json", dir=destination.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(snapshot, stream, ensure_ascii=True, separators=(",", ":"), allow_nan=False)
            stream.write("\n")
        os.replace(temporary, destination)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def validate_public_snapshot(snapshot):
    """Reject extra fields before a JSON file can enter the public build."""
    def fields(value, expected):
        if not isinstance(value, dict) or set(value) != set(expected):
            raise ValueError("Snapshot contains unexpected or missing public fields.")
    flags = snapshot.get("includes", {})
    fields(flags, ("revenue", "financials", "balance"))
    if any(type(value) is not bool for value in flags.values()):
        raise ValueError("Snapshot metric flags must be boolean.")
    keys = {"schemaVersion", "generatedAt", "group", "coverage", "itemsOnSale", "includes", "items", "daily"}
    if flags["financials"]:
        keys.add("financials")
        fields(snapshot.get("financials"), ("funds", "pending", "sales_month", "updated"))
    if flags["balance"]:
        keys.add("accountBalance")
        fields(snapshot.get("accountBalance"), ("robux", "asOf"))
    fields(snapshot, keys)
    fields(snapshot["group"], ("id", "name"))
    fields(snapshot["coverage"], ("firstRecordedDay", "lastRecordedDay", "syncedThrough"))
    fields(snapshot["itemsOnSale"], ("count", "asOf"))
    if snapshot["schemaVersion"] != 1:
        raise ValueError("Unsupported public snapshot version.")
    for item in snapshot["items"]:
        fields(item, ("key", "assetId", "name"))
    for day in snapshot["daily"]:
        fields(day, ("date", "items"))
        for entry in day["items"]:
            fields(entry, {"key", "sales", "inGame", "website", "other"} |
                   ({"earnedRobux"} if flags["revenue"] else set()))


def main():
    local_root = Path(os.environ.get("LOCALAPPDATA", Path.home()))
    default_db = local_root / "RospritesPrivate" / "better-ugc-analytics-tool" / "data" / "sales.db"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=default_db)
    parser.add_argument("--group-id", type=int)
    parser.add_argument("--group-name", default="My Roblox group")
    parser.add_argument("--include-revenue", action="store_true")
    parser.add_argument("--include-financials", action="store_true", help="Also enables revenue")
    parser.add_argument("--include-balance", action="store_true", help="Publish personal account balance separately")
    parser.add_argument("--output", type=Path, default=ROOT / "data" / "ugc-stats.json")
    args = parser.parse_args()
    try:
        snapshot = export_snapshot(args.db, group_id=args.group_id, group_name=args.group_name,
                                   revenue=args.include_revenue, financials=args.include_financials,
                                   balance=args.include_balance)
        write_snapshot(snapshot, args.output)
    except (ValueError, OSError, sqlite3.Error) as error:
        parser.exit(1, f"Export failed: {error}\n")
    print(f"Public aggregate snapshot written to {args.output.resolve()}")
    print("Only this generated JSON belongs on the website; keep the source database private.")


if __name__ == "__main__":
    main()
