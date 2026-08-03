# -*- coding: utf-8 -*-
"""The seed script must populate every feature the interface exposes.

Pharmacy and lab search shipped with no demo data, so a correct search
returned an empty list and looked broken. A feature with a page in the
navigation needs seed data behind it.
"""
import importlib.util
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
