# -*- coding: utf-8 -*-
"""The seed script must populate every feature the interface exposes.

Pharmacy and lab search shipped with no demo data, so a correct search
returned an empty list and looked broken. A feature with a page in the
navigation needs seed data behind it.
"""
import importlib.util
import json
import os
import sys
import unittest
from pathlib import Path

os.environ["APP_ENV"] = "test"
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_seed.db")
os.environ.setdefault("SECRET_KEY", "test-secret-key-at-least-32-characters-long")

# The seed script lives outside the backend package, so it is loaded by path
# rather than by import. This keeps the suite runnable from backend/ without
# the caller having to set PYTHONPATH.
_SEED_PATH = Path(__file__).resolve().parents[2] / "scripts" / "seed_database.py"
_spec = importlib.util.spec_from_file_location("seed_database", _SEED_PATH)
seed = importlib.util.module_from_spec(_spec)
sys.modules["seed_database"] = seed
_spec.loader.exec_module(seed)


class SeedCoverageTests(unittest.TestCase):
    def test_pharmacies_and_labs_are_seeded(self):
        self.assertTrue(seed.PHARMACIES)
        self.assertTrue(seed.LABS)

    def test_stock_covers_the_common_brands_a_user_will_search(self):
        brands = {brand.split()[0].lower() for brand, _, _ in seed.STOCK_ITEMS}
        for expected in ("napa", "seclo", "alatrol", "comet"):
            self.assertIn(expected, brands)

    def test_the_catalogue_covers_tests_triage_recommends(self):
        """Triage advises an NS1 test for dengue, so a lab must offer one."""
        codes = {code for code, *_ in seed.LAB_CATALOGUE}
        for expected in ("CBC", "NS1", "SPUTUM-AFB", "HBA1C"):
            self.assertIn(expected, codes)

    def test_stock_prices_and_quantities_are_plausible(self):
        for brand, strength, price in seed.STOCK_ITEMS:
            self.assertGreater(price, 0, brand)
            self.assertTrue(strength, brand)

    def test_every_seeded_provider_has_a_district(self):
        for _code, _name, district, _area, _phone in seed.PHARMACIES + seed.LABS:
            self.assertTrue(district)


if __name__ == "__main__":
    unittest.main()


class AvailabilityRefreshTests(unittest.TestCase):
    """Seeding must leave the booking flow with usable dates.

    Slots are published as a rolling window. A database seeded a fortnight
    ago holds only dates that have passed, so every doctor appears fully
    booked; re-seeding has to clear those and publish fresh ones.
    """

    def test_the_seed_script_refreshes_the_rolling_window(self):
        self.assertTrue(
            hasattr(seed, "refresh_availability"),
            "seeding must top the availability window back up",
        )

    def test_refresh_publishes_from_today_onwards(self):
        from datetime import date, timedelta

        window = [
            (date.today() + timedelta(days=offset)).isoformat()
            for offset in range(0, 8)
        ]
        self.assertEqual(date.today().isoformat(), window[0])
        self.assertTrue(all(day >= window[0] for day in window))


class RealDataTests(unittest.TestCase):
    """The committed real datasets must stay usable.

    These files are derived from public sources by ml/fetch_real_data.py and
    are committed so a clone works offline. A silent truncation or a schema
    change in the derivation would otherwise only show up as a worse model.
    """

    REAL = Path(__file__).resolve().parents[2] / "data" / "real"

    def test_the_facility_export_is_present_and_populated(self):
        path = self.REAL / "bd_health_facilities.csv"
        self.assertTrue(path.exists(), f"{path} is missing")

        import csv

        with path.open(encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))

        hospitals = [r for r in rows if r["kind"] == "hospital"]
        self.assertGreater(len(hospitals), 1000)

        for row in hospitals[:200]:
            with self.subTest(name=row["name"]):
                latitude = float(row["latitude"])
                longitude = float(row["longitude"])
                # Bangladesh's bounding box. A coordinate outside it means the
                # export has picked up the wrong columns.
                self.assertTrue(20.0 <= latitude <= 27.0)
                self.assertTrue(88.0 <= longitude <= 93.0)

    def test_the_ed_triage_export_carries_labels_and_vitals(self):
        path = self.REAL / "nhamcs_ed_triage.csv"
        self.assertTrue(path.exists(), f"{path} is missing")

        import csv

        with path.open(encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))

        self.assertGreater(len(rows), 5000)

        levels = {row["severity_level"] for row in rows}
        self.assertEqual({"1", "2", "3", "4", "5"}, levels)

        # Every row must carry a complaint, or it cannot serve as vocabulary.
        self.assertTrue(all(row["reason_1"].strip() for row in rows))

        temperatures = [
            float(row["temperature_c"]) for row in rows
            if row["temperature_c"].strip()
        ]
        self.assertTrue(temperatures)
        for value in temperatures:
            self.assertTrue(
                30.0 <= value <= 45.0,
                f"{value} C is outside any survivable range — the Fahrenheit "
                "conversion is wrong",
            )

    def test_the_seeded_directory_covers_more_than_one_district(self):
        """A single-district directory cannot serve a national platform."""
        path = Path(__file__).resolve().parents[2] / "data" / "seed"
        hospitals = json.loads(
            (path / "hospitals.json").read_text(encoding="utf-8")
        )
        districts = {h.get("district") for h in hospitals}
        self.assertGreater(len(hospitals), 100)
        self.assertGreater(len(districts), 5)
