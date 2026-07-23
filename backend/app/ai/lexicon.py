# -*- coding: utf-8 -*-
"""BanglaMed-AI lexicon.

Curated multilingual (Bangla / Banglish-romanized / English) medical surface
forms for symptom spotting, plus duration, qualifier and demographic cues.
This single source of truth is shared by the synthetic-dataset generator
(``ml/generate_triage_dataset.py``) and the runtime entity extractor
(``backend/app/ai/extraction.py``).

Triage levels (per SasthoSetu Enhanced Platform doc, section 4.2):
    1 = Self-care    2 = Teleconsult    3 = GP visit
    4 = Specialist   5 = Emergency
"""

TRIAGE_LABELS = {
    1: "self_care",
    2: "teleconsult",
    3: "gp_visit",
    4: "specialist",
    5: "emergency",
}

CARE_PATHWAYS = {
    1: {"en": "Self-care at home with rest and hydration",
        "bn": "বাসায় বিশ্রাম ও পর্যাপ্ত পানি পান করে নিজের যত্ন নিন"},
    2: {"en": "Teleconsultation with a doctor within 24 hours",
        "bn": "২৪ ঘণ্টার মধ্যে টেলিমেডিসিনে ডাক্তারের পরামর্শ নিন"},
    3: {"en": "Visit a general physician within 1-2 days",
        "bn": "১-২ দিনের মধ্যে জেনারেল ফিজিশিয়ান দেখান"},
    4: {"en": "See the recommended specialist as soon as possible",
        "bn": "যত দ্রুত সম্ভব বিশেষজ্ঞ ডাক্তার দেখান"},
    5: {"en": "EMERGENCY - go to the nearest hospital emergency department NOW",
        "bn": "জরুরি অবস্থা - এখনই নিকটস্থ হাসপাতালের জরুরি বিভাগে যান"},
}

# canonical_symptom: {surface forms per language, default specialty, base triage level}
from .lexicon_symptoms import SYMPTOMS

# Intensity qualifiers -----------------------------------------------------
QUALIFIERS = {
    "severe": {
        "bn": ["খুব বেশি", "তীব্র", "অনেক", "প্রচণ্ড", "অসহ্য", "মারাত্মক"],
        "bl": ["khub beshi", "onek beshi", "tibro", "oshojjho"],
        "en": ["severe", "very bad", "unbearable", "extreme", "too much"],
    },
    "mild": {
        "bn": ["হালকা", "অল্প", "সামান্য", "একটু"],
        "bl": ["halka", "olpo", "ektu", "shamanno"],
        "en": ["mild", "slight", "a little", "light"],
    },
    "intermittent": {
        "bn": ["মাঝে মাঝে", "থেমে থেমে", "কখনো কখনো"],
        "bl": ["majhe majhe", "theme theme"],
        "en": ["sometimes", "on and off", "occasionally"],
    },
}

# Durations: (bn, banglish, en, days) -------------------------------------
DURATIONS = [
    ("আজ সকাল থেকে", "aj shokal theke", "since this morning", 0),
    ("আজ থেকে", "aj theke", "since today", 0),
    ("গতকাল থেকে", "gotokal theke", "since yesterday", 1),
    ("দুই দিন ধরে", "dui din dhore", "for 2 days", 2),
    ("২ দিন ধরে", "2 din dhore", "for two days", 2),
    ("তিন দিন ধরে", "tin din dhore", "for 3 days", 3),
    ("৩ দিন ধরে", "3 din dhore", "for three days", 3),
    ("চার দিন ধরে", "char din dhore", "for 4 days", 4),
    ("পাঁচ দিন ধরে", "pach din dhore", "for 5 days", 5),
    ("এক সপ্তাহ ধরে", "ek shoptaho dhore", "for a week", 7),
    ("১০ দিন ধরে", "10 din dhore", "for 10 days", 10),
    ("দুই সপ্তাহ ধরে", "dui shoptaho dhore", "for 2 weeks", 14),
    ("তিন সপ্তাহ ধরে", "tin shoptaho dhore", "for 3 weeks", 21),
    ("এক মাস ধরে", "ek mash dhore", "for a month", 30),
    ("দুই মাস ধরে", "dui mash dhore", "for 2 months", 60),
]

BN_DIGITS = {"০": "0", "১": "1", "২": "2", "৩": "3", "৪": "4",
             "৫": "5", "৬": "6", "৭": "7", "৮": "8", "৯": "9"}

BN_NUM_WORDS = {
    "এক": 1, "দুই": 2, "তিন": 3, "চার": 4, "পাঁচ": 5, "ছয়": 6,
    "সাত": 7, "আট": 8, "নয়": 9, "দশ": 10, "পনের": 15, "বিশ": 20, "ত্রিশ": 30,
    "ek": 1, "dui": 2, "tin": 3, "char": 4, "pach": 5, "choy": 6,
    "shat": 7, "at": 8, "noy": 9, "dosh": 10,
}

GREETINGS = {
    "bn": ["", "", "আসসালামু আলাইকুম। ", "ডাক্তার সাহেব, ", "হ্যালো ডাক্তার, ", "ভাইয়া, "],
    "bl": ["", "", "assalamu alaikum, ", "doctor, ", "hello doctor, ", "vaiya, "],
    "en": ["", "", "Hello doctor, ", "Hi, ", "Doctor, "],
}

TRAILERS = {
    "bn": ["", "", " কী করব?", " কোন ডাক্তার দেখাবো?", " খুব চিন্তায় আছি।", " একটু পরামর্শ দিন।"],
    "bl": ["", "", " ki korbo?", " kon doctor dekhabo?", " please help.", " ektu poramorsho din."],
    "en": ["", "", " What should I do?", " Which doctor should I see?", " Please advise."],
}

SPECIALTIES = sorted({v["specialty"] for v in SYMPTOMS.values()})
