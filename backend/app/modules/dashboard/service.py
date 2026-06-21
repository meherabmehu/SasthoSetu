from sqlalchemy.orm import Session

from app.models.patient import Patient
from app.models.doctor import Doctor
from app.models.appointment import Appointment
from app.models.prescription import Prescription
from app.models.medical_record import MedicalRecord


def get_dashboard_stats_service(
    db: Session
):

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

    return {
        "total_patients": total_patients,
        "total_doctors": total_doctors,
        "verified_doctors": verified_doctors,
        "pending_doctors": pending_doctors,
        "total_appointments": total_appointments,
        "completed_appointments": completed_appointments,
        "cancelled_appointments": cancelled_appointments,
        "total_prescriptions": total_prescriptions,
        "total_medical_records": total_medical_records
    }