from fastapi import FastAPI

from app.core.database import engine
from app.models.base import Base

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
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="SasthoSetu API",
    version="1.0.0"
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