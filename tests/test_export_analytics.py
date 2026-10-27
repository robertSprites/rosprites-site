import importlib.util
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from contextlib import closing
from datetime import datetime, timezone

spec = importlib.util.spec_from_file_location("export_analytics", Path(__file__).resolve().parents[1] / "tools" / "export_analytics.py")
exporter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(exporter)


class ExportPrivacyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "sales.db"
        with closing(sqlite3.connect(self.path)) as db:
            db.executescript("""
                CREATE TABLE sales (id TEXT, source TEXT, created TEXT, asset_id INTEGER,
                    asset_name TEXT, buyer_id INTEGER, robux INTEGER, location TEXT);
                CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);
            """)
            db.executemany("INSERT INTO sales VALUES (?,?,?,?,?,?,?,?)", [
                ("PRIVATE-TRANSACTION-ONE", "group:123", "2026-10-25T12:34:56.123Z", 4, "Hat", 987654321, 30, "Game"),
                ("PRIVATE-TRANSACTION-TWO", "group:123", "2026-10-25T12:35:56.123Z", 4, "Hat", 987654322, 20, "Website"),
                ("PRIVATE-PERSONAL-SALE", "user", "2026-10-25T12:34:56.123Z", 5, "PRIVATE-PERSONAL-ITEM", 12345, 999, "Game"),
            ])
            db.executemany("INSERT INTO meta VALUES (?,?)", [
                ("cookie", '"PRIVATE-COOKIE-SENTINEL"'),
                ("balance", json.dumps({"robux": 123456, "ts": 123, "private": "PRIVATE-METADATA"})),
                ("financials", json.dumps({"group:123": {"funds": 500, "pending": 100, "updated": 123, "error": "PRIVATE-ERROR"}})),
                ("catalog", json.dumps({"group:123": {"items": 2, "as_of": 123, "error": "PRIVATE-ERROR"}})),
            ])
            db.commit()

    def export(self, **options):
        return exporter.export_snapshot(self.path, now=datetime(2026, 10, 26, tzinfo=timezone.utc), **options)

    def test_default_export_has_no_money_or_private_rows(self):
        result = self.export()
        text = json.dumps(result)
        for sensitive in ["PRIVATE", "buyer", "transaction", "12:34:56", "earnedRobux", "accountBalance", '"funds"', '"pending"']:
            self.assertNotIn(sensitive, text)
        self.assertEqual(result["daily"][0]["items"][0]["sales"], 2)
        self.assertEqual(len(result["items"]), 1)

    def test_opted_in_financials_are_aggregated_and_allowlisted(self):
        result = self.export(financials=True, balance=True)
        self.assertEqual(result["daily"][0]["items"][0]["earnedRobux"], 50)
        self.assertEqual(result["financials"]["funds"], 500)
        self.assertEqual(result["accountBalance"]["robux"], 123456)
        self.assertNotIn("PRIVATE", json.dumps(result))

    def test_multiple_groups_require_selection_and_never_mix(self):
        with closing(sqlite3.connect(self.path)) as db:
            db.execute("INSERT INTO sales VALUES ('other','group:456','2026-10-25T00:00:00Z',8,'Other',1,90,'Game')")
            db.commit()
        with self.assertRaises(ValueError):
            self.export()
        result = self.export(group_id=123, revenue=True)
        self.assertEqual(len(result["items"]), 1)

    def test_missing_database_is_not_created(self):
        missing = self.path.parent / "missing.db"
        with self.assertRaises(ValueError):
            exporter.export_snapshot(missing)
        self.assertFalse(missing.exists())

    def test_unknown_revenue_remains_unknown(self):
        with closing(sqlite3.connect(self.path)) as db:
            db.execute("UPDATE sales SET robux=NULL WHERE id='PRIVATE-TRANSACTION-TWO'")
            db.commit()
        self.assertIsNone(self.export(revenue=True)["daily"][0]["items"][0]["earnedRobux"])

    def test_public_build_rejects_extra_private_fields(self):
        snapshot = self.export(financials=True, balance=True)
        exporter.validate_public_snapshot(snapshot)
        snapshot["cookie"] = "PRIVATE-COOKIE-SENTINEL"
        with self.assertRaises(ValueError):
            exporter.validate_public_snapshot(snapshot)
        del snapshot["cookie"]
        snapshot["daily"][0]["items"][0]["buyer_id"] = 987654321
        with self.assertRaises(ValueError):
            exporter.validate_public_snapshot(snapshot)


if __name__ == "__main__":
    unittest.main()
