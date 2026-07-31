# -*- coding: utf-8 -*-
"""FHIR R4 resource mapping.

Bangladesh's Digital Health Strategy mandates FHIR-based interoperability, so
records are exposed as standard R4 resources rather than a bespoke shape. That
lets any conformant government or hospital system consume SasthoSetu data
without a custom integration.

Resources covered: Patient, Practitioner, Encounter, Observation,
MedicationRequest, DiagnosticReport, Organization and Bundle.

Identifiers use platform-scoped systems so a resource can always be traced back
to the record it came from.
"""
from __future__ import annotations

from datetime import date, datetime, timezone

BASE_SYSTEM = "https://sasthosetu.gov.bd/fhir"

SYSTEMS = {
    "patient": f"{BASE_SYSTEM}/patient-id",
    "practitioner": f"{BASE_SYSTEM}/bmdc",
    "encounter": f"{BASE_SYSTEM}/encounter-id",
    "prescription": f"{BASE_SYSTEM}/prescription-code",
    "order": f"{BASE_SYSTEM}/lab-order",
    "organization": f"{BASE_SYSTEM}/facility-code",
}

# Triage severity expressed as a FHIR triage code.
TRIAGE_CODES = {
    1: ("self-care", "Self care"),
    2: ("teleconsult", "Teleconsultation"),
    3: ("gp-visit", "General practitioner visit"),
    4: ("specialist", "Specialist review"),
    5: ("emergency", "Emergency"),
}


def _stamp(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def patient_resource(patient, user) -> dict:
    """Map a patient profile to a FHIR Patient."""
    gender_map = {"MALE": "male", "FEMALE": "female", "OTHER": "other"}

    resource = {
        "resourceType": "Patient",
        "id": patient.id,
        "identifier": [
            {"system": SYSTEMS["patient"], "value": patient.id}
        ],
        "active": True,
        "gender": gender_map.get(
            (patient.gender or "").upper(), "unknown"
        ),
        "birthDate": _stamp(patient.date_of_birth),
    }

    if user:
        resource["name"] = [{"text": user.full_name, "use": "official"}]
        telecom = []
        if user.phone:
            telecom.append({"system": "phone", "value": user.phone, "use": "mobile"})
        if user.email:
            telecom.append({"system": "email", "value": user.email})
        if telecom:
            resource["telecom"] = telecom

    if patient.address:
        resource["address"] = [{"text": patient.address, "country": "BD"}]

    if patient.blood_group:
        resource["extension"] = [
            {
                "url": f"{BASE_SYSTEM}/StructureDefinition/blood-group",
                "valueString": patient.blood_group,
            }
        ]

    return resource


def practitioner_resource(doctor, user) -> dict:
    """Map a doctor profile to a FHIR Practitioner."""
    resource = {
        "resourceType": "Practitioner",
        "id": doctor.id,
        "identifier": [
            {
                "system": SYSTEMS["practitioner"],
                "value": doctor.bmdc_number,
                "assigner": {"display": "Bangladesh Medical and Dental Council"},
            }
        ],
        "active": bool(doctor.verification_status),
        "qualification": [
            {
                "code": {"text": doctor.specialization},
                "issuer": {"display": "BMDC"},
            }
        ],
    }
    if user:
        resource["name"] = [{"text": user.full_name, "use": "official"}]
    return resource


def organization_resource(hospital) -> dict:
    resource = {
        "resourceType": "Organization",
        "id": hospital.id,
        "identifier": [{"system": SYSTEMS["organization"], "value": hospital.code}],
        "active": bool(hospital.is_active),
        "name": hospital.name,
        "type": [
            {
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/organization-type",
                        "code": "prov",
                        "display": "Healthcare Provider",
                    }
                ]
            }
        ],
        "address": [
            {
                "text": hospital.address or hospital.area or "",
                "district": hospital.district,
                "country": "BD",
            }
        ],
    }
    if hospital.phone:
        resource["telecom"] = [{"system": "phone", "value": hospital.phone}]
    return resource


def encounter_resource(consultation, appointment=None) -> dict:
    status_map = {
        "OPEN": "in-progress",
        "COMPLETED": "finished",
        "CANCELLED": "cancelled",
    }
    resource = {
        "resourceType": "Encounter",
        "id": consultation.id,
        "identifier": [{"system": SYSTEMS["encounter"], "value": consultation.id}],
        "status": status_map.get(consultation.status, "unknown"),
        "class": {
            "system": "http://terminology.hl7.org/CodeSystem/v3-ActCode",
            "code": "VR",
            "display": "Virtual",
        },
        "subject": {"reference": f"Patient/{consultation.patient_id}"},
        "participant": [
            {
                "individual": {
                    "reference": f"Practitioner/{consultation.doctor_id}"
                }
            }
        ],
        "period": {
            "start": _stamp(consultation.started_at),
            "end": _stamp(consultation.closed_at),
        },
    }

    if consultation.chief_complaint:
        resource["reasonCode"] = [{"text": consultation.chief_complaint}]
    if consultation.diagnosis:
        resource["diagnosis"] = [
            {"condition": {"display": consultation.diagnosis}, "rank": 1}
        ]
    return resource


def triage_observation_resource(session) -> dict:
    """Map a triage assessment to a FHIR Observation."""
    code, display = TRIAGE_CODES.get(
        session.severity_level or 0, ("unknown", "Unknown")
    )
    resource = {
        "resourceType": "Observation",
        "id": session.id,
        "status": "final",
        "category": [
            {
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/observation-category",
                        "code": "survey",
                        "display": "Survey",
                    }
                ]
            }
        ],
        "code": {
            "coding": [
                {
                    "system": f"{BASE_SYSTEM}/CodeSystem/triage-severity",
                    "code": code,
                    "display": display,
                }
            ],
            "text": "Symptom triage assessment",
        },
        "effectiveDateTime": _stamp(session.created_at),
        "valueInteger": session.severity_level,
        "note": [{"text": session.input_text}],
    }

    if session.patient_id:
        resource["subject"] = {"reference": f"Patient/{session.patient_id}"}

    components = []
    for symptom in session.matched_symptoms or []:
        components.append(
            {
                "code": {"text": "Reported symptom"},
                "valueString": symptom,
            }
        )
    for flag in session.safety_flags or []:
        components.append(
            {
                "code": {"text": "Red flag"},
                "valueString": flag,
            }
        )
    if components:
        resource["component"] = components

    if session.safety_flags:
        resource["interpretation"] = [
            {
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/v3-ObservationInterpretation",
                        "code": "AA",
                        "display": "Critical abnormal",
                    }
                ]
            }
        ]
    return resource


def medication_request_resources(record, lines) -> list[dict]:
    """One MedicationRequest per prescribed medicine."""
    status = {
        "ACTIVE": "active",
        "DISPENSED": "completed",
        "CANCELLED": "cancelled",
    }.get(record.status, "unknown")

    resources = []
    for line in lines:
        resources.append(
            {
                "resourceType": "MedicationRequest",
                "id": line.id,
                "identifier": [
                    {
                        "system": SYSTEMS["prescription"],
                        "value": record.verification_code,
                    }
                ],
                "status": status,
                "intent": "order",
                "medicationCodeableConcept": {
                    "text": line.medicine_name,
                    "coding": (
                        [
                            {
                                "system": f"{BASE_SYSTEM}/CodeSystem/generic",
                                "code": line.generic_name,
                                "display": line.generic_name,
                            }
                        ]
                        if line.generic_name
                        else []
                    ),
                },
                "subject": {"reference": f"Patient/{record.patient_id}"},
                "requester": {"reference": f"Practitioner/{record.doctor_id}"},
                "authoredOn": _stamp(record.issued_at),
                "dosageInstruction": [
                    {
                        "text": (
                            f"{line.strength or ''} {line.frequency} "
                            f"for {line.duration}"
                        ).strip(),
                        "timing": {"code": {"text": line.frequency}},
                        "route": {"text": line.route},
                        "patientInstruction": line.instructions or "",
                    }
                ],
                "dispenseRequest": {
                    "validityPeriod": {
                        "start": _stamp(record.issued_at),
                        "end": _stamp(record.valid_until),
                    }
                },
            }
        )
    return resources


def diagnostic_report_resource(order, test=None) -> dict:
    status = {
        "REQUESTED": "registered",
        "ACCEPTED": "registered",
        "SAMPLE_COLLECTED": "partial",
        "PROCESSING": "partial",
        "REPORTED": "final",
        "CANCELLED": "cancelled",
    }.get(order.status, "unknown")

    resource = {
        "resourceType": "DiagnosticReport",
        "id": order.id,
        "identifier": [{"system": SYSTEMS["order"], "value": order.order_code}],
        "status": status,
        "code": {"text": test.name if test else "Laboratory test"},
        "subject": {"reference": f"Patient/{order.patient_id}"},
        "performer": [{"reference": f"Organization/{order.provider_id}"}],
        "effectiveDateTime": _stamp(order.collected_at or order.created_at),
    }

    if order.status == "REPORTED":
        resource["issued"] = _stamp(order.reported_at)
        resource["conclusion"] = order.result_summary
        if order.is_abnormal:
            resource["conclusionCode"] = [{"text": "Abnormal result"}]
    return resource


def bundle(resources: list[dict], bundle_type: str = "collection") -> dict:
    """Wrap resources in a FHIR Bundle."""
    return {
        "resourceType": "Bundle",
        "type": bundle_type,
        "timestamp": _stamp(datetime.now(timezone.utc)),
        "total": len(resources),
        "entry": [
            {
                "fullUrl": f"{BASE_SYSTEM}/{r['resourceType']}/{r['id']}",
                "resource": r,
            }
            for r in resources
        ],
    }


def capability_statement(version: str) -> dict:
    """Minimal CapabilityStatement describing what this server exposes."""
    resources = [
        "Patient",
        "Practitioner",
        "Organization",
        "Encounter",
        "Observation",
        "MedicationRequest",
        "DiagnosticReport",
    ]
    return {
        "resourceType": "CapabilityStatement",
        "status": "active",
        "date": _stamp(datetime.now(timezone.utc)),
        "publisher": "SasthoSetu",
        "kind": "instance",
        "software": {"name": "SasthoSetu FHIR API", "version": version},
        "fhirVersion": "4.0.1",
        "format": ["application/fhir+json"],
        "rest": [
            {
                "mode": "server",
                "documentation": (
                    "Read-only FHIR R4 access to SasthoSetu clinical records. "
                    "Access is scoped to the authenticated subject."
                ),
                "resource": [
                    {
                        "type": name,
                        "interaction": [{"code": "read"}, {"code": "search-type"}],
                    }
                    for name in resources
                ],
            }
        ],
    }
