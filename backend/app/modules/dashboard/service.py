from sqlalchemy.orm import Session

from app.models.consultation import Consultation
from app.models.patient import Patient
from app.models.prescription_item import PrescriptionRecord
from app.models.triage_session import TriageSession
from app.models.user import User
from app.models.doctor import Doctor
from app.models.appointment import Appointment
from app.models.prescription import Prescription
from app.models.medical_record import MedicalRecord


def get_dashboard_stats_service(
    db: Session
):

    total_users = (
        db.query(User)
        .count()
    )

    total_patients = (
        db.query(Patient)
        .count()
    )

    total_doctors = (
        db.query(Doctor)
        .count()
    )

    verified_doctors = (
        db.query(Doctor)
        .filter(
            Doctor.verification_status == True
        )
        .count()
    )

    pending_doctors = (
        db.query(Doctor)
        .filter(
            Doctor.verification_status == False
        )
        .count()
    )

    total_appointments = (
        db.query(Appointment)
        .count()
    )

    completed_appointments = (
        db.query(Appointment)
        .filter(
            Appointment.status == "COMPLETED"
        )
        .count()
    )

    cancelled_appointments = (
        db.query(Appointment)
        .filter(
            Appointment.status == "CANCELLED"
        )
        .count()
    )

    total_prescriptions = (
        db.query(Prescription)
        .count()
    )

    total_medical_records = (
        db.query(MedicalRecord)
        .count()
    )

    total_triage_sessions = (
        db.query(TriageSession)
        .count()
    )

    emergency_triage_sessions = (
        db.query(TriageSession)
        .filter(
            TriageSession.severity_level == 5
        )
        .count()
    )

    total_consultations = (
        db.query(Consultation)
        .count()
    )

    signed_prescriptions = (
        db.query(PrescriptionRecord)
        .count()
    )

    dispensed_prescriptions = (
        db.query(PrescriptionRecord)
        .filter(
            PrescriptionRecord.status == "DISPENSED"
        )
        .count()
    )

    return {
        "total_users": total_users,
        "total_patients": total_patients,
        "total_doctors": total_doctors,
        "verified_doctors": verified_doctors,
        "pending_doctors": pending_doctors,
        "total_appointments": total_appointments,
        "completed_appointments": completed_appointments,
        "cancelled_appointments": cancelled_appointments,
        "total_prescriptions": total_prescriptions,
        "total_medical_records": total_medical_records,
        "total_triage_sessions": total_triage_sessions,
        "emergency_triage_sessions": emergency_triage_sessions,
        "total_consultations": total_consultations,
        "signed_prescriptions": signed_prescriptions,
        "dispensed_prescriptions": dispensed_prescriptions
    }