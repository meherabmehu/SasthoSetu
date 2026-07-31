import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.core.middleware import (
    RateLimitMiddleware,
    RequestContextMiddleware,
    SecurityHeadersMiddleware,
)

from app.modules.users.routes import router as user_router
from app.modules.auth.routes import router as auth_router
from app.models.patient import Patient
from app.modules.patients.routes import router as patient_router
from app.models.doctor import Doctor
from app.modules.doctors.routes import (
    router as doctor_router
)
from app.models.appointment import Appointment
from app.modules.appointments.routes import (
    router as appointment_router
)
from app.models.prescription import Prescription
from app.modules.prescriptions.routes import (
    router as prescription_router
)
from app.models.medical_record import MedicalRecord
from app.modules.medical_records.routes import (
    router as medical_record_router
)
from app.models.doctor_availability import DoctorAvailability
from app.modules.doctor_availability.routes import (
    router as doctor_availability_router
)
from app.modules.dashboard.routes import (
    router as dashboard_router
)
from app.modules.patient_history.routes import (
    router as patient_history_router
)
from app.models.notification import Notification

from app.modules.notifications.routes import (
    router as notification_router
)
from app.modules.admin.routes import (
    router as admin_router
)
from app.models.file_record import FileRecord

from app.modules.files.routes import (
    router as file_router
)
from app.modules.symptom_checker.routes import (
    router as symptom_checker_router
)
from app.models.hospital import (
    BedStatusHistory,
    Hospital,
    HospitalStaff,
    Ward,
)
from app.modules.hospitals.routes import (
    router as hospital_router
)
from app.models.triage_session import TriageSession
from app.modules.triage_sessions.routes import (
    router as triage_session_router
)
from app.models.consultation import Consultation, ConsultationMessage
from app.models.prescription_item import (
    PrescriptionLine,
    PrescriptionRecord,
)
from app.modules.consultations.routes import (
    router as consultation_router
)
from app.models.provider import (
    LabOrder,
    LabTest,
    PharmacyStock,
    Provider,
)
from app.modules.providers.routes import (
    router as provider_router
)
from app.models.payment import Payment
from app.modules.payments.routes import (
    router as payment_router
)
from app.modules.fhir.routes import (
    router as fhir_router
)
from app.models.ai_feedback import AIFeedback
from app.modules.ai.routes import (
    router as ai_router
)

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    debug=settings.debug,
    description=(
        "AI-assisted health platform for Bangladesh: bilingual triage, "
        "doctor matching, consultations, verifiable prescriptions, hospital "
        "capacity, labs, pharmacies, payments and FHIR R4 interoperability."
    ),
)

# Middleware runs bottom-up, so rate limiting is evaluated before the handler
# and request logging wraps everything.
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(RequestContextMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials="*" not in settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID", "X-Response-Time-ms"],
)

app.include_router(
    user_router,
    prefix="/api/v1",
    tags=["Users"]
)

app.include_router(
    auth_router,
    prefix="/api/v1/auth",
    tags=["Authentication"]
)

app.include_router(
    patient_router,
    prefix="/api/v1",
    tags=["Patients"]
)
app.include_router(
    doctor_router,
    prefix="/api/v1",
    tags=["Doctors"]
)

app.include_router(
    appointment_router,
    prefix="/api/v1",
    tags=["Appointments"]
)
# Registered before the legacy prescription router: the static /prescriptions
# paths here would otherwise be captured by /prescriptions/{doctor_id}.
app.include_router(
    consultation_router,
    prefix="/api/v1",
    tags=["Consultations"]
)
app.include_router(
    prescription_router,
    prefix="/api/v1",
    tags=["Prescriptions"]
)
app.include_router(
    medical_record_router,
    prefix="/api/v1",
    tags=["Medical Records"]
)
app.include_router(
    doctor_availability_router,
    prefix="/api/v1",
    tags=["Doctor Availability"]
)
app.include_router(
    dashboard_router,
    prefix="/api/v1",
    tags=["Dashboard"]
)
app.include_router(
    patient_history_router,
    prefix="/api/v1",
    tags=["Patient History"]
)
app.include_router(
    notification_router,
    prefix="/api/v1",
    tags=["Notifications"]
)
app.include_router(
    admin_router,
    prefix="/api/v1",
    tags=["Admin"]
)
app.include_router(
    file_router,
    prefix="/api/v1",
    tags=["Files"]
)
app.include_router(
    symptom_checker_router,
    prefix="/api/v1",
    tags=["AI Health Assistant"]
)
app.include_router(
    hospital_router,
    prefix="/api/v1",
    tags=["Hospitals"]
)
app.include_router(
    triage_session_router,
    prefix="/api/v1",
    tags=["Triage Sessions"]
)
app.include_router(
    provider_router,
    prefix="/api/v1",
    tags=["Labs & Pharmacies"]
)
app.include_router(
    payment_router,
    prefix="/api/v1",
    tags=["Payments"]
)
app.include_router(
    fhir_router,
    prefix="/api/v1",
    tags=["FHIR Interoperability"]
)
app.include_router(
    ai_router,
    prefix="/api/v1",
    tags=["BanglaMed-AI"]
)
@app.get("/")
def root():
    return {
        "message": "SasthoSetu API Running"
    }


@app.get("/health")
def health_check():
    return {
        "status": "healthy"
    }