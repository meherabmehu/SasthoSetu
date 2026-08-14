# -*- coding: utf-8 -*-
"""Roll doctor consulting slots forward so the booking flow always has dates.

Published availability is a rolling window, not a fixed set of dates. A
database seeded a fortnight ago holds only slots that have already passed, so
every doctor appears fully booked and no appointment can be made. This tops
the window back up and removes slots that have expired unused.

Idempotent: re-running it neither duplicates slots nor disturbs booked ones.

    python scripts/refresh_availability.py [--days 7]
"""
from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.database import SessionLocal  # noqa: E402
from app.models.doctor import Doctor  # noqa: E402
from app.models.doctor_availability import DoctorAvailability  # noqa: E402

# Used when a doctor has no historical pattern to copy, so a newly verified
# doctor still becomes bookable.
DEFAULT_SLOTS = ["09:00", "10:00", "11:00", "16:00", "17:00", "18:00"]


def _slot_pattern(db, doctor_id: str) -> list[str]:
    """The times this doctor usually consults, newest pattern first."""

    times = [
        row[0]
        for row in db.query(DoctorAvailability.start_time)
        .filter(DoctorAvailability.doctor_id == doctor_id)
        .distinct()
        .all()
    ]
    return sorted(times) or DEFAULT_SLOTS


def refresh(days: int = 7) -> tuple[int, int]:
    db = SessionLocal()
    created = 0
    removed = 0

    try:
        today = date.today().isoformat()

        # An unbooked slot in the past can never be used; a booked one is kept
        # because it is the record of an appointment that took place.
        removed = (
            db.query(DoctorAvailability)
            .filter(
                DoctorAvailability.available_date < today,
                DoctorAvailability.is_booked == False,  # noqa: E712
            )
            .delete(synchronize_session=False)
        )

        upcoming = [
            (date.today() + timedelta(days=offset)).isoformat()
            for offset in range(0, days + 1)
        ]

        for doctor in db.query(Doctor).all():
            pattern = _slot_pattern(db, doctor.id)

            existing = {
                (row.available_date, row.start_time)
                for row in db.query(DoctorAvailability)
                .filter(DoctorAvailability.doctor_id == doctor.id)
                .all()
            }

            for day in upcoming:
                for start in pattern:
                    if (day, start) in existing:
                        continue

                    hour, minute = start.split(":")
                    db.add(
                        DoctorAvailability(
                            doctor_id=doctor.id,
                            available_date=day,
                            start_time=start,
                            end_time=f"{(int(hour) + 1) % 24:02d}:{minute}",
                            is_booked=False,
                        )
                    )
                    created += 1

        db.commit()
    finally:
        db.close()

    return created, removed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--days",
        type=int,
        default=7,
        help="how many days ahead to publish (default: 7)",
    )
    args = parser.parse_args()

    created, removed = refresh(args.days)
    print(f"Done. new slots={created} expired slots removed={removed}")


if __name__ == "__main__":
    main()
