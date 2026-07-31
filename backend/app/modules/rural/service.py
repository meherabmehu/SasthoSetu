# -*- coding: utf-8 -*-
"""Rural access channels: SMS, IVR and community health workers.

Most of the people this platform exists for do not have a smartphone, a data
connection, or in many cases the literacy to use one. Those users are served
through the channels they already have: a feature phone that can receive SMS
and dial a number, and a community health worker who visits in person.

Design constraints that shape everything here:

* **SMS is 160 characters.** Bangla in UCS-2 gets 70 per segment, so replies
  are composed against a character budget and truncated on a word boundary
  rather than mid-word.
* **IVR has no screen.** Menus are numeric, shallow, and every branch reaches
  an outcome within a few key presses.
* **A CHW visit is offline.** Assessments are captured on a tablet with no
  connectivity and submitted as a batch when the worker next reaches a signal,
  so the payload accepts many records at once and reports per-record results
  instead of failing the whole batch.
"""
from __future__ import annotations

from fastapi import HTTPException

from sqlalchemy.orm import Session

from app.ai.extraction import extract
from app.ai.safety import check_red_flags
from app.models.patient import Patient
from app.models.triage_session import TriageSession
from app.models.user import User
from app.modules.symptom_checker.service import triage_symptoms
from app.schemas.triage import TriageRequest

# A single Bangla SMS segment is 70 characters; two segments stay affordable.
SMS_BUDGET = 140

EMERGENCY_SMS = {
    "bn": "জরুরি! এখনই নিকটস্থ হাসপাতালের জরুরি বিভাগে যান বা ৯৯৯ কল করুন।",
    "en": "EMERGENCY. Go to the nearest hospital now or call 999.",
}

LEVEL_SMS = {
    1: {"bn": "ঘরে বিশ্রাম ও পানি পান করুন। খারাপ হলে ডাক্তার দেখান।",
        "en": "Rest at home and drink fluids. See a doctor if it worsens."},
    2: {"bn": "২৪ ঘণ্টার মধ্যে ডাক্তারের পরামর্শ নিন।",
        "en": "Get a doctor's advice within 24 hours."},
    3: {"bn": "১-২ দিনের মধ্যে ডাক্তার দেখান।",
        "en": "See a doctor within 1-2 days."},
    4: {"bn": "দ্রুত বিশেষজ্ঞ ডাক্তার দেখান।",
        "en": "See a specialist as soon as possible."},
    5: EMERGENCY_SMS,
}

# IVR menu. Each option maps to a phrase the same extractor understands, so
# the phone channel and the app channel reach identical conclusions.
IVR_MENU = {
    "root": {
        "prompt": {
            "bn": "সাস্থ্যসেতুতে স্বাগতম। উপসর্গ বেছে নিতে চাপুন: "
                  "১ জ্বর, ২ বুকে ব্যথা বা শ্বাসকষ্ট, ৩ পেটের সমস্যা, "
                  "৪ মাথা ব্যথা, ৫ শিশুর সমস্যা, ০ অপারেটর।",
            "en": "Welcome to SasthoSetu. Press 1 fever, 2 chest pain or "
                  "breathing difficulty, 3 stomach problem, 4 headache, "
                  "5 child illness, 0 operator.",
        },
        "options": {
            "1": "fever",
            "2": "cardio",
            "3": "abdominal",
            "4": "headache",
            "5": "child",
            "0": "operator",
        },
    },
    "fever": {
        "prompt": {
            "bn": "জ্বরের সাথে ঘাড় শক্ত হলে ১, শুধু জ্বর হলে ২, "
                  "জ্বর ও কাশি হলে ৩ চাপুন।",
            "en": "Press 1 if fever with stiff neck, 2 for fever alone, "
                  "3 for fever with cough.",
        },
        "options": {
            "1": "তীব্র জ্বর এবং ঘাড় শক্ত",
            "2": "জ্বর",
            "3": "জ্বর এবং কাশি",
        },
        "terminal": True,
    },
    "cardio": {
        "prompt": {
            "bn": "বুকে ব্যথার সাথে শ্বাসকষ্ট হলে ১, শুধু বুকে ব্যথা হলে ২, "
                  "শুধু শ্বাসকষ্ট হলে ৩ চাপুন।",
            "en": "Press 1 for chest pain with breathlessness, 2 chest pain "
                  "only, 3 breathlessness only.",
        },
        "options": {
            "1": "বুকে ব্যথা এবং শ্বাস নিতে কষ্ট",
            "2": "বুকে ব্যথা",
            "3": "শ্বাস নিতে কষ্ট",
        },
        "terminal": True,
    },
    "abdominal": {
        "prompt": {
            "bn": "পেট ব্যথার সাথে রক্ত বমি হলে ১, বমি ও পাতলা পায়খানা হলে ২, "
                  "শুধু পেট ব্যথা হলে ৩ চাপুন।",
            "en": "Press 1 for abdominal pain with blood in vomit, "
                  "2 vomiting and diarrhoea, 3 abdominal pain only.",
        },
        "options": {
            "1": "পেট ব্যথা এবং রক্ত বমি",
            "2": "বমি এবং পাতলা পায়খানা",
            "3": "পেট ব্যথা",
        },
        "terminal": True,
    },
    "headache": {
        "prompt": {
            "bn": "হঠাৎ তীব্র মাথাব্যথা হলে ১, মুখ বেঁকে গেলে বা কথা জড়ালে ২, "
                  "সাধারণ মাথাব্যথা হলে ৩ চাপুন।",
            "en": "Press 1 sudden severe headache, 2 facial droop or slurred "
                  "speech, 3 ordinary headache.",
        },
        "options": {
            "1": "হঠাৎ তীব্র মাথাব্যথা",
            "2": "মুখ বেঁকে গেছে এবং কথা জড়িয়ে যাচ্ছে",
            "3": "মাথা ব্যথা",
        },
        "terminal": True,
    },
    "child": {
        "prompt": {
            "bn": "শিশুর খিঁচুনি হলে ১, তীব্র জ্বর হলে ২, "
                  "পাতলা পায়খানা ও বমি হলে ৩ চাপুন।",
            "en": "Press 1 if the child has convulsions, 2 high fever, "
                  "3 diarrhoea and vomiting.",
        },
        "options": {
            "1": "শিশুর খিঁচুনি",
            "2": "শিশুর তীব্র জ্বর",
            "3": "শিশুর পাতলা পায়খানা এবং বমি",
        },
        # An IVR caller cannot be asked to type an age reliably, and a fever
        # in an infant is the presentation that must not be missed. Absent a
        # stated age, a call about a child is assessed as an infant: this
        # deliberately over-escalates some older children rather than
        # under-triaging a baby.
        "age": 0,
        "terminal": True,
    },
}


def _fit(text: str, budget: int = SMS_BUDGET) -> str:
    """Trim to the SMS budget on a word boundary."""
    if len(text) <= budget:
        return text
    clipped = text[: budget - 1]
    if " " in clipped:
        clipped = clipped.rsplit(" ", 1)[0]
    return clipped + "…"


def compose_sms_reply(result, language: str = "bn") -> str:
    """Build the SMS body for a triage outcome."""
    level = {
        "SELF_CARE": 1,
        "TELECONSULT": 2,
        "GP_VISIT": 3,
        "SPECIALIST": 4,
        "EMERGENCY": 5,
    }[result.triage_level.value]

    advice = LEVEL_SMS[level][language]

    if level == 5:
        # Nothing is appended to an emergency message: every character spent
        # on detail is a character that could push the instruction into a
        # second segment that may not arrive.
        return _fit(advice)

    specialty = result.recommended_specialty
    suffix = (
        f" বিভাগ: {specialty}." if language == "bn" else f" Specialty: {specialty}."
    )
    return _fit(advice + suffix)


def sms_triage_service(payload, db: Session):
    """Handle an inbound SMS and return the reply to send back."""
    request = TriageRequest(
        symptoms=payload.text,
        age_years=payload.age_years,
    )
    result = triage_symptoms(request)

    user = None
    if payload.phone:
        user = db.query(User).filter(User.phone == payload.phone).first()

    patient = (
        db.query(Patient).filter(Patient.user_id == user.id).first() if user else None
    )

    session = TriageSession(
        patient_id=patient.id if patient else None,
        user_id=user.id if user else None,
        input_text=payload.text,
        language=payload.language,
        age_years=payload.age_years,
        engine="sms",
        model_version="rules-v1.1",
        triage_level=result.triage_level.value,
        severity_level={
            "SELF_CARE": 1, "TELECONSULT": 2, "GP_VISIT": 3,
            "SPECIALIST": 4, "EMERGENCY": 5,
        }[result.triage_level.value],
        possible_condition=result.possible_condition,
        recommended_specialty=result.recommended_specialty,
        confidence=float(result.confidence),
        matched_symptoms=result.matched_symptoms,
        safety_flags=result.safety_flags,
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    reply = compose_sms_reply(result, payload.language)
    return {
        "reply": reply,
        "segments": (len(reply) // 70) + 1,
        "characters": len(reply),
        "triage_level": result.triage_level.value,
        "is_emergency": result.triage_level.value == "EMERGENCY",
        "triage_session_id": session.id,
    }


def ivr_menu_service(node: str, language: str = "bn"):
    """Return an IVR node: its prompt and the keys the caller may press."""
    entry = IVR_MENU.get(node)
    if not entry:
        raise HTTPException(status_code=404, detail="Unknown IVR node")

    return {
        "node": node,
        "prompt": entry["prompt"][language],
        "options": sorted(entry["options"]),
        "is_terminal": bool(entry.get("terminal")),
    }


def ivr_select_service(payload, db: Session):
    """Apply a keypress. Returns either the next prompt or a triage outcome."""
    entry = IVR_MENU.get(payload.node)
    if not entry:
        raise HTTPException(status_code=404, detail="Unknown IVR node")

    selection = entry["options"].get(payload.digit)
    if selection is None:
        return {
            "node": payload.node,
            "prompt": entry["prompt"][payload.language],
            "options": sorted(entry["options"]),
            "error": (
                "ভুল নম্বর, আবার চেষ্টা করুন।"
                if payload.language == "bn"
                else "Invalid choice, please try again."
            ),
        }

    if selection == "operator":
        return {
            "node": "operator",
            "transfer_to_operator": True,
            "prompt": (
                "একজন প্রতিনিধির সাথে সংযোগ করা হচ্ছে।"
                if payload.language == "bn"
                else "Connecting you to an operator."
            ),
        }

    # A non-terminal node moves the caller one level deeper.
    if not entry.get("terminal"):
        return ivr_menu_service(selection, payload.language)

    age = payload.age_years if payload.age_years is not None else entry.get("age")
    result = triage_symptoms(TriageRequest(symptoms=selection, age_years=age))

    session = TriageSession(
        input_text=selection,
        language=payload.language,
        age_years=age,
        engine="ivr",
        model_version="rules-v1.1",
        triage_level=result.triage_level.value,
        severity_level={
            "SELF_CARE": 1, "TELECONSULT": 2, "GP_VISIT": 3,
            "SPECIALIST": 4, "EMERGENCY": 5,
        }[result.triage_level.value],
        possible_condition=result.possible_condition,
        recommended_specialty=result.recommended_specialty,
        confidence=float(result.confidence),
        matched_symptoms=result.matched_symptoms,
        safety_flags=result.safety_flags,
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    spoken = (
        result.advice_bn if payload.language == "bn" else result.advice
    ) or result.advice

    return {
        "node": "result",
        "is_terminal": True,
        "triage_level": result.triage_level.value,
        "is_emergency": result.triage_level.value == "EMERGENCY",
        "prompt": spoken,
        "recommended_specialty": result.recommended_specialty,
        "triage_session_id": session.id,
        # An emergency call is escalated rather than simply announced.
        "transfer_to_operator": result.triage_level.value == "EMERGENCY",
    }


def chw_batch_service(payload, current_user, db: Session):
    """Accept a batch of offline community health worker assessments.

    Each record is processed independently: one malformed entry must not
    discard a whole day of fieldwork.
    """
    accepted = []
    rejected = []

    for index, record in enumerate(payload.assessments):
        try:
            request = TriageRequest(
                symptoms=record.symptoms,
                age_years=record.age_years,
                temperature_c=record.temperature_c,
            )
            result = triage_symptoms(request)

            entities = extract(record.symptoms)
            flags = check_red_flags(entities.symptoms, record.age_years)

            session = TriageSession(
                input_text=record.symptoms,
                language=record.language,
                age_years=record.age_years,
                temperature_c=record.temperature_c,
                engine="chw",
                model_version="rules-v1.1",
                triage_level=result.triage_level.value,
                severity_level={
                    "SELF_CARE": 1, "TELECONSULT": 2, "GP_VISIT": 3,
                    "SPECIALIST": 4, "EMERGENCY": 5,
                }[result.triage_level.value],
                possible_condition=result.possible_condition,
                recommended_specialty=result.recommended_specialty,
                confidence=float(result.confidence),
                matched_symptoms=result.matched_symptoms,
                safety_flags=result.safety_flags,
                latitude=record.latitude,
                longitude=record.longitude,
                user_id=current_user.get("user_id"),
            )
            db.add(session)
            db.flush()

            accepted.append(
                {
                    "client_reference": record.client_reference,
                    "triage_session_id": session.id,
                    "triage_level": result.triage_level.value,
                    "is_emergency": bool(flags),
                    "recommended_specialty": result.recommended_specialty,
                }
            )
        except Exception as error:  # noqa: BLE001 - reported, never fatal
            rejected.append(
                {
                    "index": index,
                    "client_reference": getattr(record, "client_reference", None),
                    "reason": str(error),
                }
            )

    db.commit()

    # Emergencies found during a home visit are the reason this channel exists,
    # so they are surfaced at the top of the response for immediate follow-up.
    urgent = [item for item in accepted if item["is_emergency"]]

    return {
        "accepted": len(accepted),
        "rejected": len(rejected),
        "emergencies": urgent,
        "results": accepted,
        "errors": rejected,
    }
