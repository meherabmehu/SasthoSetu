from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.dependencies import get_db
from app.core.security import get_current_user

from app.fhir import mapping
from app.models.consultation import Consultation
from app.models.doctor import Doctor
from app.models.hospital import Hospital
from app.models.patient import Patient
from app.models.prescription_item import PrescriptionLine, PrescriptionRecord
from app.models.provider import LabOrder, LabTest
from app.models.triage_session import TriageSession
from app.models.user import User

router = APIRouter()


def _assert_patient_access(patient: Patient, current_user, db: Session):
    """A record may be read by its subject, a clinician or an administrator."""
    role = current_user.get("role")
    if role in ("ADMIN", "DOCTOR"):
        return
    if patient.user_id != current_user.get("user_id"):
        raise HTTPException(
            status_code=403, detail="Not authorised to read this record"
        )


def _patient_or_404(patient_id: str, db: Session) -> Patient:
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    return patient


@router.get("/fhir/metadata")
def capability_statement():
    """FHIR conformance statement for this server."""
    return mapping.capability_statement(settings.app_version)


@router.get("/fhir/Patient/{patient_id}")
def read_patient(
    patient_id: str,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    patient = _patient_or_404(patient_id, db)
    _assert_patient_access(patient, current_user, db)
    user = db.query(User).filter(User.id == patient.user_id).first()
    return mapping.patient_resource(patient, user)


@router.get("/fhir/Practitioner/{doctor_id}")
def read_practitioner(doctor_id: str, db: Session = Depends(get_db)):
    doctor = db.query(Doctor).filter(Doctor.id == doctor_id).first()
    if not doctor:
        raise HTTPException(status_code=404, detail="Practitioner not found")
    user = db.query(User).filter(User.id == doctor.user_id).first()
    return mapping.practitioner_resource(doctor, user)


@router.get("/fhir/Organization/{hospital_id}")
def read_organization(hospital_id: str, db: Session = Depends(get_db)):
    hospital = db.query(Hospital).filter(Hospital.id == hospital_id).first()
    if not hospital:
        hospital = db.query(Hospital).filter(Hospital.code == hospital_id).first()
    if not hospital:
        raise HTTPException(status_code=404, detail="Organization not found")
    return mapping.organization_resource(hospital)


@router.get("/fhir/Encounter/{consultation_id}")
def read_encounter(
    consultation_id: str,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    consultation = (
        db.query(Consultation).filter(Consultation.id == consultation_id).first()
    )
    if not consultation:
        raise HTTPException(status_code=404, detail="Encounter not found")
    patient = _patient_or_404(consultation.patient_id, db)
    _assert_patient_access(patient, current_user, db)
    return mapping.encounter_resource(consultation)


@router.get("/fhir/Observation/{session_id}")
def read_observation(
    session_id: str,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    session = (
        db.query(TriageSession).filter(TriageSession.id == session_id).first()
    )
    if not session:
        raise HTTPException(status_code=404, detail="Observation not found")
    if session.patient_id:
        _assert_patient_access(_patient_or_404(session.patient_id, db), current_user, db)
    return mapping.triage_observation_resource(session)


@router.get("/fhir/MedicationRequest")
def search_medication_requests(
    patient: str,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    subject = _patient_or_404(patient, db)
    _assert_patient_access(subject, current_user, db)

    records = (
        db.query(PrescriptionRecord)
        .filter(PrescriptionRecord.patient_id == subject.id)
        .all()
    )
    resources = []
    for record in records:
        lines = (
            db.query(PrescriptionLine)
            .filter(PrescriptionLine.prescription_id == record.id)
            .order_by(PrescriptionLine.sequence.asc())
            .all()
        )
        resources.extend(mapping.medication_request_resources(record, lines))
    return mapping.bundle(resources, "searchset")


@router.get("/fhir/DiagnosticReport")
def search_diagnostic_reports(
    patient: str,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    subject = _patient_or_404(patient, db)
    _assert_patient_access(subject, current_user, db)

    orders = db.query(LabOrder).filter(LabOrder.patient_id == subject.id).all()
    resources = []
    for order in orders:
        test = db.query(LabTest).filter(LabTest.id == order.lab_test_id).first()
        resources.append(mapping.diagnostic_report_resource(order, test))
    return mapping.bundle(resources, "searchset")


@router.get("/fhir/Patient/{patient_id}/$everything")
def patient_everything(
    patient_id: str,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """The complete record for one patient as a single FHIR Bundle.

    This is the export a receiving facility needs to see a patient's history
    without a bespoke integration.
    """
    patient = _patient_or_404(patient_id, db)
    _assert_patient_access(patient, current_user, db)

    user = db.query(User).filter(User.id == patient.user_id).first()
    resources = [mapping.patient_resource(patient, user)]

    for session in (
        db.query(TriageSession).filter(TriageSession.patient_id == patient.id).all()
    ):
        resources.append(mapping.triage_observation_resource(session))

    for consultation in (
        db.query(Consultation).filter(Consultation.patient_id == patient.id).all()
    ):
        resources.append(mapping.encounter_resource(consultation))

    for record in (
        db.query(PrescriptionRecord)
        .filter(PrescriptionRecord.patient_id == patient.id)
        .all()
    ):
        lines = (
            db.query(PrescriptionLine)
            .filter(PrescriptionLine.prescription_id == record.id)
            .order_by(PrescriptionLine.sequence.asc())
            .all()
        )
        resources.extend(mapping.medication_request_resources(record, lines))

    for order in db.query(LabOrder).filter(LabOrder.patient_id == patient.id).all():
        test = db.query(LabTest).filter(LabTest.id == order.lab_test_id).first()
        resources.append(mapping.diagnostic_report_resource(order, test))

    return mapping.bundle(resources, "document")
