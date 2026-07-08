SEVERITY_PRIORITY = {
    "SELF_CARE": 1,
    "TELECONSULT": 2,
    "GP_VISIT": 3,
    "SPECIALIST": 4,
    "EMERGENCY": 5,
}


# Safety rules are evaluated before condition rules. These rules are deliberately
# conservative and must not be replaced by a probabilistic model.
EMERGENCY_RULES = [
    {
        "code": "CARDIO_RESPIRATORY_DISTRESS",
        "english": ["chest pain", "shortness of breath"],
        "bangla": ["বুকে ব্যথা", "শ্বাসকষ্ট"],
        "match": "all",
        "condition": "Possible heart or lung emergency",
        "specialty": "Emergency Medicine",
        "advice": "Call emergency services or go to the nearest emergency department now.",
    },
    {
        "code": "ALTERED_CONSCIOUSNESS",
        "english": ["unconscious", "not responding", "altered consciousness"],
        "bangla": ["অজ্ঞান", "সাড়া দিচ্ছে না", "চেতনা নেই"],
        "match": "any",
        "condition": "Altered consciousness",
        "specialty": "Emergency Medicine",
        "advice": "Call emergency services immediately. Do not give food or drink.",
    },
    {
        "code": "SEVERE_BLEEDING",
        "english": ["severe bleeding", "heavy bleeding", "bleeding won't stop"],
        "bangla": ["প্রচণ্ড রক্তপাত", "অতিরিক্ত রক্তপাত", "রক্তপাত বন্ধ হচ্ছে না"],
        "match": "any",
        "condition": "Severe bleeding",
        "specialty": "Emergency Medicine",
        "advice": "Apply firm pressure if safe and seek emergency care immediately.",
    },
    {
        "code": "MENINGITIS_WARNING",
        "english": ["high fever", "stiff neck"],
        "bangla": ["তীব্র জ্বর", "ঘাড় শক্ত"],
        "match": "all",
        "condition": "Possible serious infection",
        "specialty": "Emergency Medicine",
        "advice": "Seek emergency medical assessment immediately.",
    },
]


CONDITION_RULES = [
    {
        "english": ["fever", "body pain"],
        "bangla": ["জ্বর", "শরীর ব্যথা"],
        "match": "all",
        "severity": "SPECIALIST",
        "condition": "Possible dengue or another febrile illness",
        "specialty": "Internal Medicine",
        "advice": "Arrange an urgent medical consultation. Testing may be needed.",
    },
    {
        "english": ["fever"],
        "bangla": ["জ্বর"],
        "match": "any",
        "severity": "GP_VISIT",
        "condition": "Fever requiring assessment",
        "specialty": "General Physician",
        "advice": "Stay hydrated and consult a doctor if fever persists or worsens.",
    },
    {
        "english": ["cough", "sore throat", "runny nose"],
        "bangla": ["কাশি", "গলা ব্যথা", "নাক দিয়ে পানি"],
        "match": "any",
        "severity": "SELF_CARE",
        "condition": "Possible upper respiratory infection",
        "specialty": "General Physician",
        "advice": "Rest, drink fluids, and monitor symptoms. Consult a doctor if they worsen.",
    },
    {
        "english": ["headache"],
        "bangla": ["মাথা ব্যথা", "মাথাব্যথা"],
        "match": "any",
        "severity": "SELF_CARE",
        "condition": "Headache",
        "specialty": "General Physician",
        "advice": "Rest and stay hydrated. Seek care for severe, sudden, or persistent pain.",
    },
]
