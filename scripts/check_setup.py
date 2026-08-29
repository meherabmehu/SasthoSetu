# -*- coding: utf-8 -*-
"""Check that the database and models are in a usable state.

Seeding prints how many rows it *created*, which is zero on every run after
the first. That is correct but tells you nothing about whether the data is
right — a database can be fully seeded and still be broken, as happened when
every doctor stayed posted to a hospital that had been replaced.

This asks the questions that actually matter and answers them from the
database itself:

    python scripts/check_setup.py

Exit status is 0 when everything passes, 1 when something needs attention.
"""
from __future__ import annotations

import sys
import warnings
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from sqlalchemy import func, select  # noqa: E402

from app.core.database import SessionLocal  # noqa: E402
from app.models.doctor import Doctor  # noqa: E402
from app.models.doctor_availability import DoctorAvailability  # noqa: E402
from app.models.hospital import Hospital  # noqa: E402
from app.models.provider import Provider  # noqa: E402

ARTIFACTS = ROOT / "backend" / "app" / "ai" / "artifacts"

# A model built by a slightly different scikit-learn still loads and scores
# correctly. The warning is noise in a setup check, and hiding it here does not
# hide it from training, where the version does matter.
warnings.filterwarnings("ignore", message=".*InconsistentVersion.*")
try:
    from sklearn.exceptions import InconsistentVersionWarning

    warnings.filterwarnings("ignore", category=InconsistentVersionWarning)
except ImportError:
    pass

PASS = "  ok   "
FAIL = "  FAIL "


class Report:
    def __init__(self) -> None:
        self.failed = 0

    def check(self, label: str, ok: bool, detail: str = "",
              fix: str = "") -> None:
        print(f"{PASS if ok else FAIL}{label}"
              + (f"  {detail}" if detail else ""))
        if not ok:
            self.failed += 1
            if fix:
                print(f"         fix: {fix}")


def main() -> None:
    report = Report()
    db = SessionLocal()

    try:
        print("Facilities")
        hospitals = db.scalar(select(func.count()).select_from(Hospital)) or 0
        report.check(
            "hospitals seeded", hospitals >= 100, f"{hospitals:,}",
            "python ml/prepare_all.py && python scripts/seed_database.py",
        )

        districts = db.scalar(
            select(func.count(func.distinct(Hospital.district)))
        ) or 0
        report.check(
            "hospitals cover many districts", districts >= 5,
            f"{districts} districts",
            "python ml/build_facility_seed.py && "
            "python scripts/seed_database.py",
        )

        pharmacies = db.scalar(
            select(func.count()).select_from(Provider)
            .where(Provider.provider_type == "PHARMACY")
        ) or 0
        report.check("pharmacies seeded", pharmacies >= 5, f"{pharmacies:,}")

        print("\nDoctors")
        doctors = db.scalar(select(func.count()).select_from(Doctor)) or 0
        report.check("doctors seeded", doctors >= 10, f"{doctors}")

        postings = db.scalar(
            select(func.count(func.distinct(Doctor.hospital_name)))
        ) or 0
        # Doctors clustered on a handful of hospitals means patients outside
        # those cities have nobody nearby, even when the hospital list is full.
        report.check(
            "doctors spread across hospitals", postings >= 10,
            f"{postings} hospitals",
            "python scripts/seed_database.py  (updates existing postings)",
        )

        today = date.today().isoformat()
        bookable = db.scalar(
            select(func.count(func.distinct(DoctorAvailability.doctor_id)))
            .where(
                DoctorAvailability.available_date >= today,
                DoctorAvailability.is_booked == False,  # noqa: E712
            )
        ) or 0
        report.check(
            "doctors with a free upcoming slot", bookable >= 5,
            f"{bookable} of {doctors}",
            "python scripts/refresh_availability.py",
        )

        print("\nModels")
        for name in ("triage_model.joblib", "surge_model.joblib"):
            path = ARTIFACTS / name
            report.check(
                f"{name} present", path.exists(),
                f"{path.stat().st_size // 1024:,} KB" if path.exists() else "",
                "python ml/prepare_all.py",
            )

        if (ARTIFACTS / "triage_model.joblib").exists():
            try:
                from app.ai.triage_service import triage

                result = triage("বুকে ব্যথা, শ্বাস নিতে কষ্ট", age=55)
                level = result["severity_level"]
                # A cardiac presentation must reach level 5. Anything less
                # means the model and the lexicon have drifted apart.
                report.check(
                    "triage escalates a cardiac emergency", level == 5,
                    f"level {level}",
                    "python ml/prepare_all.py  (rebuilds against the lexicon)",
                )
            except Exception as error:  # noqa: BLE001
                report.check(
                    "triage runs", False, str(error)[:90],
                    "python ml/prepare_all.py",
                )

        print("\nReal data")
        real = ROOT / "data" / "real"
        for filename, minimum in (
            ("nhamcs_ed_triage.csv", 1000),
            ("bd_health_facilities.csv", 1000),
        ):
            path = real / filename
            if not path.exists():
                report.check(f"{filename}", False, "missing",
                             "python ml/fetch_real_data.py")
                continue
            with path.open(encoding="utf-8") as fh:
                rows = sum(1 for _ in fh) - 1
            report.check(f"{filename}", rows >= minimum, f"{rows:,} rows",
                         "python ml/fetch_real_data.py")
    finally:
        db.close()

    print()
    if report.failed:
        print(f"{report.failed} check(s) need attention — see the fixes above.")
        sys.exit(1)
    print("Everything checks out. Start the servers and sign in.")


if __name__ == "__main__":
    main()
