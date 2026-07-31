# -*- coding: utf-8 -*-
"""Deterministic triage rule tables.

Severity ordering and condition rules for the rule-based triage layer. Symptom
recognition itself is delegated to the shared BanglaMed-AI lexicon
(``app.ai.lexicon``) so that Bangla, Banglish and English surface forms stay in
one place; these rules operate on canonical symptom identifiers rather than on
raw substrings.

Emergency escalation is owned by ``app.ai.safety`` (RED_FLAG_RULES). It is not
duplicated here: a single auditable red-flag table avoids the risk of the two
layers drifting apart and disagreeing on a life-threatening presentation.
"""

SEVERITY_PRIORITY = {
    "SELF_CARE": 1,
    "TELECONSULT": 2,
    "GP_VISIT": 3,
    "SPECIALIST": 4,
    "EMERGENCY": 5,
}

LEVEL_TO_SEVERITY = {
    1: "SELF_CARE",
    2: "TELECONSULT",
    3: "GP_VISIT",
    4: "SPECIALIST",
    5: "EMERGENCY",
}


# Condition rules are expressed over canonical symptom ids from the lexicon.
# "all" requires every listed symptom; "any" requires at least one.
CONDITION_RULES = [
    {
        "code": "FEBRILE_ILLNESS_DENGUE",
        "symptoms": ["fever", "body_ache"],
        "match": "all",
        "severity": "SPECIALIST",
        "condition": "Possible dengue or another febrile illness",
        "condition_bn": "সম্ভাব্য ডেঙ্গু বা অন্য জ্বরজনিত অসুস্থতা",
        "specialty": "Internal Medicine",
        "advice": "Arrange an urgent medical consultation. Testing may be needed.",
        "advice_bn": "দ্রুত চিকিৎসকের পরামর্শ নিন। পরীক্ষা প্রয়োজন হতে পারে।",
    },
    {
        "code": "DEHYDRATION_RISK",
        "symptoms": ["diarrhea", "vomiting"],
        "match": "all",
        "severity": "GP_VISIT",
        "condition": "Diarrhoea with vomiting - dehydration risk",
        "condition_bn": "ডায়রিয়ার সাথে বমি - পানিশূন্যতার ঝুঁকি",
        "specialty": "Internal Medicine",
        "advice": "Start oral saline immediately and see a doctor today.",
        "advice_bn": "এখনই খাবার স্যালাইন শুরু করুন এবং আজই ডাক্তার দেখান।",
    },
    {
        "code": "RESPIRATORY_INFECTION",
        "symptoms": ["cough", "fever"],
        "match": "all",
        "severity": "GP_VISIT",
        "condition": "Possible lower respiratory tract infection",
        "condition_bn": "সম্ভাব্য শ্বাসনালীর সংক্রমণ",
        "specialty": "Pulmonology",
        "advice": "See a physician within 24 hours, especially if breathing worsens.",
        "advice_bn": "২৪ ঘণ্টার মধ্যে চিকিৎসক দেখান, শ্বাসকষ্ট বাড়লে দ্রুত।",
    },
    {
        "code": "FEVER_ALONE",
        "symptoms": ["fever", "high_fever"],
        "match": "any",
        "severity": "GP_VISIT",
        "condition": "Fever requiring assessment",
        "condition_bn": "জ্বর - মূল্যায়ন প্রয়োজন",
        "specialty": "General Physician",
        "advice": "Stay hydrated and consult a doctor if fever persists or worsens.",
        "advice_bn": "পর্যাপ্ত পানি পান করুন; জ্বর না কমলে ডাক্তার দেখান।",
    },
    {
        "code": "UPPER_RESPIRATORY",
        "symptoms": ["cough", "sore_throat", "runny_nose"],
        "match": "any",
        "severity": "SELF_CARE",
        "condition": "Possible upper respiratory infection",
        "condition_bn": "সম্ভাব্য ঠান্ডা-সর্দি বা গলার সংক্রমণ",
        "specialty": "General Physician",
        "advice": "Rest, drink fluids, and monitor symptoms. Consult a doctor if they worsen.",
        "advice_bn": "বিশ্রাম নিন ও পানি পান করুন। খারাপ হলে ডাক্তার দেখান।",
    },
    {
        "code": "HEADACHE",
        "symptoms": ["headache"],
        "match": "any",
        "severity": "SELF_CARE",
        "condition": "Headache",
        "condition_bn": "মাথাব্যথা",
        "specialty": "General Physician",
        "advice": "Rest and stay hydrated. Seek care for severe, sudden, or persistent pain.",
        "advice_bn": "বিশ্রাম নিন। হঠাৎ তীব্র বা দীর্ঘস্থায়ী ব্যথায় চিকিৎসা নিন।",
    },
]
