from app.schemas.symptom_checker import (
    SymptomResponse
)


def analyze_symptoms_service(
    symptoms: str
):

    text = symptoms.lower()

    # Emergency
    if (
        "chest pain" in text
        or "বুকে ব্যথা" in text
        or "shortness of breath" in text
        or "শ্বাসকষ্ট" in text
    ):
        return SymptomResponse(
            severity="EMERGENCY",
            possible_disease="Possible Heart or Lung Emergency",
            recommended_specialist="Emergency Medicine",
            recommendation="Go to the nearest hospital immediately."
        )

    # Dengue
    if (
        "fever" in text
        and "body pain" in text
    ) or (
        "জ্বর" in text
        and "শরীর ব্যথা" in text
    ):
        return SymptomResponse(
            severity="SPECIALIST",
            possible_disease="Possible Dengue",
            recommended_specialist="Medicine Specialist",
            recommendation="Get a CBC test and consult a physician immediately."
        )

    # Viral Fever
    if (
        "fever" in text
        or "জ্বর" in text
    ):
        return SymptomResponse(
            severity="CONSULT_DOCTOR",
            possible_disease="Viral Fever",
            recommended_specialist="General Physician",
            recommendation="Drink plenty of fluids and consult a doctor if fever persists."
        )

    # Common Cold
    if (
        "cough" in text
        or "কাশি" in text
        or "sore throat" in text
        or "গলা ব্যথা" in text
    ):
        return SymptomResponse(
            severity="SELF_CARE",
            possible_disease="Common Cold",
            recommended_specialist="General Physician",
            recommendation="Take rest, drink warm fluids and monitor your symptoms."
        )

    # Headache
    if (
        "headache" in text
        or "মাথা ব্যথা" in text
    ):
        return SymptomResponse(
            severity="SELF_CARE",
            possible_disease="Tension Headache",
            recommended_specialist="General Physician",
            recommendation="Rest well, stay hydrated and consult a doctor if pain continues."
        )

    return SymptomResponse(
        severity="CONSULT_DOCTOR",
        possible_disease="Unknown",
        recommended_specialist="General Physician",
        recommendation="Consult a healthcare professional for proper diagnosis."
    )