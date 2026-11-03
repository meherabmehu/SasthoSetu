"""Opt-in checks against a real PostgreSQL server, in a fresh private schema.

TEST_POSTGRES_URL must identify a disposable test database. Each run creates
and removes only its own randomly named schema, leaving other schemas alone.
"""
import os
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from threading import Barrier
from types import SimpleNamespace

from alembic import command
from alembic.config import Config
from fastapi import HTTPException
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from app.models.appointment import Appointment
from app.models.doctor import Doctor
from app.models.doctor_availability import DoctorAvailability
from app.models.patient import Patient
from app.models.user import User
from app.modules.appointments.service import create_appointment_service
from app.schemas.appointment import AppointmentCreate

URL = os.environ.get("TEST_POSTGRES_URL")
BACKEND = Path(__file__).resolve().parents[1]


@unittest.skipUnless(URL, "TEST_POSTGRES_URL is not configured")
class PostgresConcurrencyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = "qa_" + uuid.uuid4().hex
        cls.admin = create_engine(URL)
        with cls.admin.begin() as conn:
            conn.execute(text(f'CREATE SCHEMA "{cls.schema}"'))
        cls.url = make_url(URL).update_query_dict({"options": f"-csearch_path={cls.schema}"})
        cls.engine = create_engine(cls.url)
        cls.sessions = sessionmaker(bind=cls.engine)
        cls.config = Config(str(BACKEND / "alembic.ini"))
        cls.config.set_main_option("script_location", str(BACKEND / "alembic"))
        cls.config.attributes["database_url"] = cls.url.render_as_string(hide_password=False)
        command.upgrade(cls.config, "head")
        command.check(cls.config)

    @classmethod
    def tearDownClass(cls):
        cls.engine.dispose()
        # schema is always a generated qa_ + hex UUID, never an external name.
        with cls.admin.begin() as conn:
            conn.execute(text(f'DROP SCHEMA "{cls.schema}" CASCADE'))
        cls.admin.dispose()

    def test_two_patients_cannot_book_the_same_slot(self):
        day = date.today() + timedelta(days=7)
        with self.sessions() as db:
            for name, role in [("p1", "PATIENT"), ("p2", "PATIENT"), ("d", "DOCTOR")]:
                db.add(User(id=name, full_name=name, email=f"{name}@example.com", phone=name,
                             password_hash="not-used", role=role))
            db.flush()
            db.add(Doctor(id="d", user_id="d", bmdc_number="QA", specialization="Medicine",
                           experience_years=5, consultation_fee=600, hospital_name="QA",
                           verification_status=True))
            for name in ["p1", "p2"]:
                db.add(Patient(id=name, user_id=name, date_of_birth=date(1990, 1, 1), gender="F",
                                blood_group="B+", height_cm=160, weight_kg=60,
                                emergency_contact=name, address="Dhaka"))
            db.flush()
            db.add(DoctorAvailability(id="slot", doctor_id="d", available_date=day.isoformat(),
                                       start_time="10:00", end_time="11:00", is_booked=False))
            db.commit()
        barrier = Barrier(2)

        def book(patient):
            with self.sessions() as db:
                # Populate both identity maps before contention, reproducing a
                # stale initial availability read before the lock is acquired.
                db.get(DoctorAvailability, "slot")
                barrier.wait(timeout=10)
                try:
                    create_appointment_service(patient, AppointmentCreate(
                        doctor_id="d", appointment_date=day, appointment_time="10:00",
                        reason="Concurrent booking regression"), db)
                    return 200
                except HTTPException as error:
                    db.rollback()
                    return error.status_code

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(book, ["p1", "p2"]))
        self.assertEqual(1, results.count(200), results)
        self.assertTrue(any(result in {400, 409} for result in results), results)
        with self.sessions() as db:
            self.assertEqual(1, db.query(Appointment).count())

    def test_z_migrations_downgrade_and_rebuild(self):
        command.downgrade(self.config, "base")
        self.assertEqual(["alembic_version"], inspect(self.engine).get_table_names())
        command.upgrade(self.config, "head")
        command.check(self.config)

    def actors(self):
        patient_id, doctor_id = "p_" + uuid.uuid4().hex, "d_" + uuid.uuid4().hex
        with self.sessions() as db:
            for name, role in [(patient_id, "PATIENT"), (doctor_id, "DOCTOR")]:
                db.add(User(id=name, full_name=name, email=f"{name}@example.com", phone=name,
                             password_hash="not-used", role=role))
            db.flush()
            db.add(Patient(id=patient_id, user_id=patient_id, date_of_birth=date(1990, 1, 1),
                gender="F", blood_group="B+", height_cm=160, weight_kg=60,
                emergency_contact=patient_id, address="Dhaka"))
            db.add(Doctor(id=doctor_id, user_id=doctor_id, bmdc_number=doctor_id,
                specialization="Medicine", experience_years=5, consultation_fee=500,
                hospital_name="QA", verification_status=True))
            db.commit()
        return patient_id, doctor_id

    def test_concurrent_dispensing_succeeds_only_once(self):
        from app.models.prescription_item import PrescriptionRecord
        from app.modules.consultations.service import (
            _canonical_payload, dispense_prescription_service, sign_payload)
        patient, doctor = self.actors()
        code = uuid.uuid4().hex[:10].upper()
        with self.sessions() as db:
            record = PrescriptionRecord(doctor_id=doctor, patient_id=patient,
                verification_code=code, issued_at=datetime.now(timezone.utc),
                valid_until=datetime.now(timezone.utc) + timedelta(days=1))
            record.signature = sign_payload(_canonical_payload(record, []))
            db.add(record)
            db.commit()
        barrier = Barrier(2)

        def dispense(_):
            with self.sessions() as db:
                barrier.wait(timeout=10)
                try:
                    dispense_prescription_service(SimpleNamespace(verification_code=code, signature=None),
                        {"user_id": doctor, "role": "DOCTOR"}, db)
                    return 200
                except HTTPException as error:
                    db.rollback()
                    return error.status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(dispense, range(2)))
        self.assertEqual([200, 409], sorted(results))

    def test_concurrent_payment_callbacks_notify_once(self):
        from app.models.notification import Notification
        from app.models.payment import Payment
        from app.modules.payments.service import handle_callback_service
        from app.payments.gateways import get_gateway
        from app.schemas.provider import PaymentCallback
        patient, _ = self.actors()
        ref = uuid.uuid4().hex
        with self.sessions() as db:
            db.add(Payment(reference=ref, idempotency_key=ref, payer_user_id=patient,
                purpose="CONSULTATION", method="bkash", amount_bdt=100,
                platform_fee_bdt=2, payout_bdt=98, status="PENDING"))
            db.commit()
        body = {"reference": ref, "status": "COMPLETED", "gateway_reference": "demo"}
        payload = PaymentCallback(**body, signature=get_gateway("bkash").signature_for(body))
        barrier = Barrier(2)

        def callback(_):
            with self.sessions() as db:
                barrier.wait(timeout=10)
                return handle_callback_service(payload, db)["status"]
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(["COMPLETED", "COMPLETED"], list(pool.map(callback, range(2))))
        with self.sessions() as db:
            self.assertEqual(1, db.query(Notification).filter(Notification.user_id == patient).count())

    def test_concurrent_refunds_cannot_exceed_paid_amount(self):
        from app.models.payment import Payment
        from app.modules.payments.service import refund_service
        from app.schemas.provider import RefundRequest
        patient, _ = self.actors()
        ref = uuid.uuid4().hex
        with self.sessions() as db:
            payment = Payment(reference=ref, idempotency_key=ref, payer_user_id=patient,
                purpose="CONSULTATION", method="bkash", amount_bdt=100,
                platform_fee_bdt=2, payout_bdt=98, status="COMPLETED")
            db.add(payment)
            db.commit()
            payment_id = payment.id
        barrier = Barrier(2)

        def refund(_):
            with self.sessions() as db:
                barrier.wait(timeout=10)
                try:
                    refund_service(payment_id, RefundRequest(amount_bdt=80),
                                   {"user_id": patient, "role": "ADMIN"}, db)
                    return 200
                except HTTPException as error:
                    db.rollback()
                    return error.status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual([200, 400], sorted(pool.map(refund, range(2))))
        with self.sessions() as db:
            self.assertEqual(80, db.get(Payment, payment_id).refunded_amount_bdt)

    def test_shared_rate_limit_is_atomic_across_sessions(self):
        from app.core.shared_limits import check_database_limit
        barrier = Barrier(8)
        client = uuid.uuid4().hex

        def request(_):
            barrier.wait(timeout=10)
            return check_database_limit(client, 3, sessions=self.sessions, timestamp=600)
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(request, range(8)))
        self.assertEqual(3, results.count(0))
        self.assertEqual(5, results.count(60))


if __name__ == "__main__":
    unittest.main()
