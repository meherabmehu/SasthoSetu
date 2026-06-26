from app.schemas.symptom_checker import (
    SymptomResponse
)

from app.modules.symptom_checker.rules import (
    DISEASE_RULES
)


def analyze_symptoms_service(
    symptoms: str
):

    text = symptoms.lower()

    for rule in DISEASE_RULES:

        if rule["match"] == "any":

            if any(
                symptom.lower() in text
                for symptom in rule["symptoms"]
            ):
                return SymptomResponse(
                    severity=rule["severity"],
                    possible_disease=rule["name"],
                    recommended_specialist=rule["doctor"],
                    recommendation=rule["recommendation"]
                )

        elif rule["match"] == "all":

            if all(
                symptom.lower() in text
                for symptom in rule["symptoms"]
            ):
                return SymptomResponse(
                    severity=rule["severity"],
                    possible_disease=rule["name"],
                    recommended_specialist=rule["doctor"],
                    recommendation=rule["recommendation"]
                )

    return SymptomResponse(
        severity="CONSULT_DOCTOR",
        possible_disease="Unknown",
        recommended_specialist="General Physician",
        recommendation="Consult a healthcare professional for proper diagnosis."
    )