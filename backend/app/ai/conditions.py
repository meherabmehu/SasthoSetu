# -*- coding: utf-8 -*-
"""Condition knowledge base for differential reasoning.

Triage answers "how urgently"; this answers "likely what". The two are kept
separate on purpose: urgency must stay deterministic and auditable, whereas a
differential is inherently probabilistic and is always presented as a ranked
list of possibilities rather than a diagnosis.

Each condition declares:

``supporting``   symptoms that raise the score, with a weight. Weight reflects
                 how *discriminating* the symptom is, not how common: fever
                 appears in dozens of conditions so it is worth little, while
                 a stiff neck points hard at meningitis.
``required``     symptoms without which the condition is not considered at all.
``excluding``    symptoms that make the condition materially less likely.
``prior``        baseline plausibility in Bangladesh. Dengue and typhoid are
                 weighted well above conditions that are rare here, because a
                 differential that ignores local epidemiology is misleading.
``red_flag``     conditions that must never be silently dropped from the list
                 even when they score below the display cut-off.

Every condition carries a Bangla name. A patient who reads the triage result
in Bangla must not be handed an English diagnosis.
"""
from __future__ import annotations

# Seasonal weighting. Dengue in Bangladesh is overwhelmingly a monsoon and
# post-monsoon disease; treating it as equally likely in February produces a
# differential that a local clinician would immediately distrust.
SEASONAL_PRIOR = {
    "dengue": {6: 1.4, 7: 1.8, 8: 2.0, 9: 2.0, 10: 1.7, 11: 1.2},
    "chikungunya": {6: 1.3, 7: 1.5, 8: 1.6, 9: 1.5, 10: 1.2},
    "malaria": {6: 1.3, 7: 1.4, 8: 1.4, 9: 1.3, 10: 1.2},
    "diarrhoeal_disease": {3: 1.3, 4: 1.5, 5: 1.4, 6: 1.3},
    "typhoid": {3: 1.2, 4: 1.4, 5: 1.4, 6: 1.3, 7: 1.2},
    "influenza": {11: 1.3, 12: 1.4, 1: 1.4, 2: 1.3},
    "pneumonia": {11: 1.2, 12: 1.4, 1: 1.4, 2: 1.3},
    "asthma_exacerbation": {10: 1.2, 11: 1.3, 12: 1.3, 1: 1.3},
}

CONDITIONS = {
    # ---------------------------------------------------------------- cardiac
    "acute_coronary_syndrome": {
        "en": "Possible heart attack (acute coronary syndrome)",
        "bn": "সম্ভাব্য হার্ট অ্যাটাক",
        "specialty": "Cardiology",
        "required": ["chest_pain"],
        "supporting": {
            "chest_pain": 3.0, "shortness_of_breath": 2.5, "palpitations": 1.2,
            "dizziness": 0.8, "vomiting": 0.5, "weakness": 0.6,
        },
        "excluding": ["sore_throat", "runny_nose"],
        "prior": 0.7,
        "red_flag": True,
        "acuity": 1,
        "advice_en": "Do not travel alone. Go to an emergency department now.",
        "advice_bn": "একা যাবেন না। এখনই জরুরি বিভাগে যান।",
    },
    "heart_failure": {
        "en": "Possible heart failure",
        "bn": "সম্ভাব্য হৃদযন্ত্রের দুর্বলতা",
        "specialty": "Cardiology",
        "required": ["shortness_of_breath"],
        "supporting": {
            "shortness_of_breath": 2.0, "swelling_legs": 2.5, "swelling": 1.5,
            "fatigue": 1.0, "palpitations": 0.8,
        },
        "excluding": ["fever", "sore_throat"],
        "prior": 0.6,
        "red_flag": True,
        "acuity": 2,
        "advice_en": "Needs urgent cardiology assessment.",
        "advice_bn": "দ্রুত হৃদরোগ বিশেষজ্ঞের পরামর্শ প্রয়োজন।",
    },
    "hypertensive_urgency": {
        "en": "Uncontrolled high blood pressure",
        "bn": "অনিয়ন্ত্রিত উচ্চ রক্তচাপ",
        "specialty": "Cardiology",
        "required": ["high_bp"],
        "supporting": {
            "high_bp": 3.0, "headache": 1.2, "blurred_vision": 1.5,
            "dizziness": 1.0, "chest_pain": 1.0,
        },
        "prior": 1.2,
        "advice_en": "Have your blood pressure measured today.",
        "advice_bn": "আজই রক্তচাপ মাপান।",
    },
    # --------------------------------------------------------------- neuro
    "stroke": {
        "en": "Possible stroke",
        "bn": "সম্ভাব্য স্ট্রোক",
        "specialty": "Neurology",
        # A focal sign is mandatory. Dizziness and blurred vision are far too
        # common to raise a stroke alert alone, and a red flag that fires on
        # ordinary symptoms trains people to ignore it.
        "required": [
            "facial_droop", "slurred_speech", "one_sided_numbness",
            "sudden_severe_headache",
        ],
        "supporting": {
            "facial_droop": 3.5, "slurred_speech": 3.0,
            "one_sided_numbness": 3.0, "sudden_severe_headache": 1.5,
            "blurred_vision": 1.0, "dizziness": 0.8, "weakness": 1.0,
        },
        "prior": 0.7,
        "red_flag": True,
        "acuity": 1,
        "advice_en": "Treatment is time-critical. Reach a hospital immediately.",
        "advice_bn": "চিকিৎসা যত দ্রুত, ফল তত ভালো। এখনই হাসপাতালে যান।",
    },
    "meningitis": {
        "en": "Possible meningitis",
        "bn": "সম্ভাব্য মেনিনজাইটিস",
        "specialty": "Neurology",
        "required": ["stiff_neck"],
        "supporting": {
            "stiff_neck": 3.5, "high_fever": 2.5, "fever": 1.5,
            "headache": 2.0, "vomiting": 1.2, "seizure": 1.5,
        },
        "prior": 0.5,
        "red_flag": True,
        "acuity": 1,
        "advice_en": "A medical emergency. Go to hospital now.",
        "advice_bn": "জরুরি অবস্থা। এখনই হাসপাতালে যান।",
    },
    "migraine": {
        "en": "Migraine",
        "bn": "মাইগ্রেন",
        "specialty": "Neurology",
        "required": ["headache"],
        "supporting": {
            "headache": 2.5, "vomiting": 1.0, "blurred_vision": 1.2,
            "dizziness": 0.6,
        },
        "excluding": ["fever", "high_fever", "stiff_neck"],
        "prior": 1.3,
        "advice_en": "Rest in a dark quiet room. See a doctor if attacks recur.",
        "advice_bn": "অন্ধকার শান্ত ঘরে বিশ্রাম নিন। বারবার হলে ডাক্তার দেখান।",
    },
    "tension_headache": {
        "en": "Tension headache",
        "bn": "টেনশন থেকে মাথাব্যথা",
        "specialty": "General Medicine",
        "required": ["headache"],
        "supporting": {
            "headache": 2.0, "insomnia": 1.2, "anxiety": 1.5, "fatigue": 0.8,
        },
        "excluding": ["fever", "high_fever", "vomiting", "stiff_neck"],
        "prior": 1.5,
        "advice_en": "Rest, hydration and reduced screen time usually help.",
        "advice_bn": "বিশ্রাম, পানি পান ও কম স্ক্রিন ব্যবহার সাহায্য করে।",
    },
    # ----------------------------------------------------- febrile illnesses
    "dengue": {
        "en": "Possible dengue fever",
        "bn": "সম্ভাব্য ডেঙ্গু জ্বর",
        "specialty": "Internal Medicine",
        "required": [],
        "supporting": {
            "high_fever": 2.5, "fever": 2.0, "body_ache": 2.5,
            "headache": 1.5, "rash": 2.0, "skin_rash": 1.8,
            "vomiting": 1.0, "eye_pain": 2.0, "weakness": 0.8,
        },
        "excluding": ["runny_nose", "sore_throat"],
        "prior": 1.8,
        "advice_en": "Get a dengue NS1 test. Drink fluids and avoid ibuprofen.",
        "advice_bn": "ডেঙ্গু NS1 পরীক্ষা করান। প্রচুর পানি পান করুন, "
                     "আইবুপ্রোফেন এড়িয়ে চলুন।",
    },
    "typhoid": {
        "en": "Possible typhoid fever",
        "bn": "সম্ভাব্য টাইফয়েড জ্বর",
        "specialty": "Internal Medicine",
        "required": [],
        "supporting": {
            "high_fever": 2.2, "fever": 2.0, "abdominal_pain": 1.8,
            "headache": 1.0, "diarrhea": 1.2, "weakness": 1.2,
            "fatigue": 1.0,
        },
        "prior": 1.5,
        "advice_en": "A blood culture is needed. Do not self-medicate with antibiotics.",
        "advice_bn": "রক্ত পরীক্ষা প্রয়োজন। নিজে থেকে অ্যান্টিবায়োটিক নেবেন না।",
    },
    "malaria": {
        "en": "Possible malaria",
        "bn": "সম্ভাব্য ম্যালেরিয়া",
        "specialty": "Internal Medicine",
        "required": [],
        "supporting": {
            "high_fever": 2.2, "fever": 2.0, "body_ache": 1.5,
            "headache": 1.2, "vomiting": 1.0, "night_sweats": 2.0,
            "weakness": 1.0,
        },
        "prior": 0.8,
        "advice_en": "Ask for a malaria test, especially after travel to hill districts.",
        "advice_bn": "ম্যালেরিয়া পরীক্ষা করান, বিশেষত পাহাড়ি এলাকায় গিয়ে থাকলে।",
    },
    "chikungunya": {
        "en": "Possible chikungunya",
        "bn": "সম্ভাব্য চিকুনগুনিয়া",
        "specialty": "Internal Medicine",
        "required": [],
        "supporting": {
            "fever": 2.0, "joint_pain": 3.0, "body_ache": 1.5,
            "rash": 1.5, "headache": 0.8,
        },
        "prior": 0.9,
        "advice_en": "Joint pain may persist for weeks. Paracetamol is preferred.",
        "advice_bn": "জয়েন্টের ব্যথা কয়েক সপ্তাহ থাকতে পারে। প্যারাসিটামল নিন।",
    },
    "influenza": {
        "en": "Influenza (seasonal flu)",
        "bn": "ইনফ্লুয়েঞ্জা (মৌসুমি ফ্লু)",
        "specialty": "General Medicine",
        "required": [],
        "supporting": {
            "fever": 2.0, "cough": 2.0, "sore_throat": 1.8,
            "runny_nose": 1.8, "body_ache": 1.5, "headache": 1.0,
            "fatigue": 1.0,
        },
        "prior": 1.4,
        "advice_en": "Rest and fluids. See a doctor if breathing becomes difficult.",
        "advice_bn": "বিশ্রাম ও পানি। শ্বাসকষ্ট হলে ডাক্তার দেখান।",
    },
    "common_cold": {
        "en": "Common cold",
        "bn": "সাধারণ সর্দি-কাশি",
        "specialty": "General Medicine",
        "required": [],
        "supporting": {
            "runny_nose": 2.5, "sore_throat": 2.0, "cough": 1.5,
        },
        "excluding": ["high_fever", "shortness_of_breath", "chest_pain"],
        "prior": 1.6,
        "advice_en": "Usually settles in a week without medicine.",
        "advice_bn": "সাধারণত এক সপ্তাহে ওষুধ ছাড়াই ভালো হয়ে যায়।",
    },
    # ------------------------------------------------------------ respiratory
    "pneumonia": {
        "en": "Possible pneumonia",
        "bn": "সম্ভাব্য নিউমোনিয়া",
        "specialty": "Pulmonology",
        "required": [],
        "supporting": {
            "cough": 2.2, "high_fever": 2.2, "fever": 1.5,
            "shortness_of_breath": 2.5, "chest_pain": 1.5, "weakness": 0.8,
        },
        "prior": 1.0,
        "red_flag": True,
        "acuity": 2,
        "advice_en": "A chest X-ray is likely needed. See a doctor today.",
        "advice_bn": "বুকের এক্স-রে প্রয়োজন হতে পারে। আজই ডাক্তার দেখান।",
    },
    "tuberculosis": {
        "en": "Possible tuberculosis",
        "bn": "সম্ভাব্য যক্ষ্মা",
        "specialty": "Pulmonology",
        "required": ["cough"],
        "supporting": {
            "cough": 2.0, "weight_loss": 3.0, "night_sweats": 3.0,
            "fever": 1.2, "fatigue": 1.0, "weakness": 1.0,
        },
        "prior": 1.2,
        "duration_days_min": 14,
        "advice_en": "A cough lasting over two weeks needs a TB test. "
                     "Testing and treatment are free at government facilities.",
        "advice_bn": "দুই সপ্তাহের বেশি কাশি হলে যক্ষ্মা পরীক্ষা করান। "
                     "সরকারি হাসপাতালে পরীক্ষা ও চিকিৎসা বিনামূল্যে।",
    },
    "asthma_exacerbation": {
        "en": "Possible asthma attack",
        "bn": "সম্ভাব্য হাঁপানির টান",
        "specialty": "Pulmonology",
        "required": ["shortness_of_breath"],
        "supporting": {
            "shortness_of_breath": 3.0, "cough": 1.5, "chest_pain": 0.8,
        },
        "excluding": ["high_fever"],
        "prior": 1.1,
        "red_flag": True,
        "acuity": 2,
        "advice_en": "Use your inhaler. Seek urgent care if it does not help.",
        "advice_bn": "ইনহেলার নিন। না কমলে দ্রুত চিকিৎসা নিন।",
    },
    # -------------------------------------------------------- gastrointestinal
    "acute_gastroenteritis": {
        "en": "Acute gastroenteritis",
        "bn": "পেটের সংক্রমণ (ডায়রিয়া ও বমি)",
        "specialty": "Internal Medicine",
        "required": [],
        "supporting": {
            "diarrhea": 2.8, "vomiting": 2.2, "abdominal_pain": 1.5,
            "fever": 0.8, "weakness": 0.8,
        },
        "prior": 1.6,
        "advice_en": "Start oral saline immediately to prevent dehydration.",
        "advice_bn": "পানিশূন্যতা এড়াতে এখনই খাবার স্যালাইন শুরু করুন।",
    },
    "cholera": {
        "en": "Possible cholera",
        "bn": "সম্ভাব্য কলেরা",
        "specialty": "Internal Medicine",
        "required": ["diarrhea"],
        "supporting": {
            "diarrhea": 3.0, "vomiting": 2.0, "weakness": 2.0,
            "dizziness": 1.5,
        },
        "excluding": ["high_fever"],
        "prior": 0.6,
        "red_flag": True,
        "acuity": 2,
        "advice_en": "Severe watery diarrhoea needs urgent rehydration at a facility.",
        "advice_bn": "প্রচুর পাতলা পায়খানা হলে দ্রুত হাসপাতালে স্যালাইন নিন।",
    },
    "peptic_ulcer": {
        "en": "Possible peptic ulcer or gastritis",
        "bn": "সম্ভাব্য গ্যাস্ট্রিক আলসার",
        "specialty": "Gastroenterology",
        "required": [],
        "supporting": {
            "abdominal_pain": 2.5, "heartburn": 3.0, "vomiting": 1.0,
        },
        "excluding": ["diarrhea", "high_fever"],
        "prior": 1.5,
        "advice_en": "Avoid spicy food and painkillers. See a doctor if it persists.",
        "advice_bn": "ঝাল খাবার ও ব্যথানাশক এড়িয়ে চলুন। না কমলে ডাক্তার দেখান।",
    },
    "upper_gi_bleed": {
        "en": "Possible internal bleeding",
        "bn": "সম্ভাব্য অভ্যন্তরীণ রক্তক্ষরণ",
        "specialty": "Gastroenterology",
        "required": [],
        "supporting": {
            "blood_vomiting": 3.5, "bloody_stool": 3.0,
            "abdominal_pain": 1.2, "weakness": 1.5, "dizziness": 1.2,
        },
        "prior": 0.5,
        "red_flag": True,
        "acuity": 1,
        "advice_en": "Go to an emergency department now. Do not eat or drink.",
        "advice_bn": "এখনই জরুরি বিভাগে যান। কিছু খাবেন না।",
    },
    "hepatitis": {
        "en": "Possible hepatitis (liver inflammation)",
        "bn": "সম্ভাব্য হেপাটাইটিস (লিভারের প্রদাহ)",
        "specialty": "Gastroenterology",
        "required": ["jaundice"],
        "supporting": {
            "jaundice": 3.5, "fatigue": 1.5, "abdominal_pain": 1.5,
            "vomiting": 1.2, "fever": 0.8, "weight_loss": 0.8,
        },
        "prior": 1.0,
        "advice_en": "Liver function tests are needed. Avoid paracetamol and alcohol.",
        "advice_bn": "লিভার ফাংশন পরীক্ষা প্রয়োজন। প্যারাসিটামল ও মদ এড়িয়ে চলুন।",
    },
    "appendicitis": {
        "en": "Possible appendicitis",
        "bn": "সম্ভাব্য অ্যাপেন্ডিসাইটিস",
        "specialty": "Internal Medicine",
        "required": ["abdominal_pain"],
        "supporting": {
            "abdominal_pain": 3.0, "vomiting": 1.8, "fever": 1.2,
        },
        "excluding": ["diarrhea", "cough", "runny_nose"],
        "prior": 0.7,
        "red_flag": True,
        "acuity": 2,
        "advice_en": "Needs urgent surgical assessment. Do not eat or drink.",
        "advice_bn": "দ্রুত সার্জিক্যাল মূল্যায়ন প্রয়োজন। কিছু খাবেন না।",
    },
    # --------------------------------------------------------------- metabolic
    "diabetes": {
        "en": "Possible diabetes",
        "bn": "সম্ভাব্য ডায়াবেটিস",
        "specialty": "Endocrinology",
        "required": [],
        "supporting": {
            "excessive_thirst": 3.0, "frequent_urination": 3.0,
            "diabetes_symptoms": 3.0, "weight_loss": 1.5,
            "fatigue": 1.2, "blurred_vision": 1.2,
        },
        "prior": 1.4,
        "advice_en": "Ask for a fasting blood glucose or HbA1c test.",
        "advice_bn": "খালি পেটে রক্তে সুগার বা HbA1c পরীক্ষা করান।",
    },
    # ---------------------------------------------------------------- urinary
    "urinary_tract_infection": {
        "en": "Urinary tract infection",
        "bn": "প্রস্রাবের সংক্রমণ",
        "specialty": "Urology",
        "required": [],
        "supporting": {
            "burning_urination": 3.0, "frequent_urination": 2.0,
            "abdominal_pain": 1.2, "fever": 1.0, "blood_in_urine": 2.0,
        },
        "prior": 1.3,
        "advice_en": "Drink plenty of water. A urine test is needed.",
        "advice_bn": "প্রচুর পানি পান করুন। প্রস্রাব পরীক্ষা প্রয়োজন।",
    },
    "kidney_disease": {
        "en": "Possible kidney problem",
        "bn": "সম্ভাব্য কিডনির সমস্যা",
        "specialty": "Nephrology",
        "required": [],
        "supporting": {
            "swelling": 2.5, "swelling_legs": 2.5, "blood_in_urine": 2.0,
            "fatigue": 1.0, "high_bp": 1.5, "weakness": 0.8,
        },
        "prior": 0.9,
        "advice_en": "Kidney function tests are needed.",
        "advice_bn": "কিডনি ফাংশন পরীক্ষা প্রয়োজন।",
    },
    # ------------------------------------------------------------- obstetric
    "obstetric_emergency": {
        "en": "Pregnancy emergency",
        "bn": "গর্ভাবস্থার জরুরি অবস্থা",
        "specialty": "Gynaecology & Obstetrics",
        # Requires a pregnancy-specific symptom. Abdominal pain and dizziness
        # alone must never surface a pregnancy condition, which would be both
        # clinically wrong and distressing to the reader.
        "required": ["pregnancy_bleeding", "pregnancy_pain"],
        "supporting": {
            "pregnancy_bleeding": 3.5, "pregnancy_pain": 2.5,
            "abdominal_pain": 1.0, "dizziness": 1.0,
        },
        "prior": 0.8,
        "red_flag": True,
        "acuity": 1,
        "advice_en": "Go to a maternity facility immediately.",
        "advice_bn": "এখনই মাতৃসদন বা হাসপাতালে যান।",
    },
    "possible_pregnancy": {
        "en": "Possible pregnancy",
        "bn": "সম্ভাব্য গর্ভধারণ",
        "specialty": "Gynaecology & Obstetrics",
        "required": ["missed_period"],
        "supporting": {
            "missed_period": 3.0, "vomiting": 1.5, "fatigue": 1.0,
        },
        "prior": 1.2,
        "advice_en": "A pregnancy test will confirm. Begin antenatal care early.",
        "advice_bn": "প্রেগন্যান্সি টেস্ট করান। দ্রুত প্রসবপূর্ব সেবা শুরু করুন।",
    },
    # ------------------------------------------------------- musculoskeletal
    "arthritis": {
        "en": "Joint inflammation (arthritis)",
        "bn": "বাত বা জয়েন্টের প্রদাহ",
        "specialty": "Orthopedics",
        "required": ["joint_pain"],
        "supporting": {
            "joint_pain": 3.0, "swelling": 1.5, "body_ache": 1.0,
        },
        "excluding": ["high_fever"],
        "prior": 1.2,
        "advice_en": "See an orthopaedic doctor if pain limits movement.",
        "advice_bn": "চলাফেরায় সমস্যা হলে অর্থোপেডিক ডাক্তার দেখান।",
    },
    "mechanical_back_pain": {
        "en": "Mechanical back pain",
        "bn": "কোমর বা পিঠের ব্যথা",
        "specialty": "Orthopedics",
        "required": ["back_pain"],
        "supporting": {"back_pain": 3.0, "joint_pain": 0.8},
        "excluding": ["fever", "high_fever", "blood_in_urine"],
        "prior": 1.4,
        "advice_en": "Gentle movement helps more than bed rest.",
        "advice_bn": "সম্পূর্ণ বিশ্রামের চেয়ে হালকা নড়াচড়া বেশি উপকারী।",
    },
    # ------------------------------------------------------------ mental health
    "anxiety_disorder": {
        "en": "Anxiety",
        "bn": "উদ্বেগজনিত সমস্যা",
        "specialty": "Psychiatry",
        "required": [],
        "supporting": {
            "anxiety": 3.0, "palpitations": 1.5, "insomnia": 2.0,
            "dizziness": 0.8, "fatigue": 0.8,
        },
        "excluding": ["fever", "high_fever"],
        "prior": 1.2,
        "advice_en": "Talking to a professional helps. This is a treatable condition.",
        "advice_bn": "বিশেষজ্ঞের সাথে কথা বললে উপকার হয়। এটি চিকিৎসাযোগ্য।",
    },
    "depression": {
        "en": "Low mood or depression",
        "bn": "বিষণ্ণতা",
        "specialty": "Psychiatry",
        "required": ["low_mood"],
        "supporting": {
            "low_mood": 3.0, "insomnia": 1.8, "fatigue": 1.5,
            "weight_loss": 1.0, "anxiety": 1.0,
        },
        "prior": 1.1,
        "advice_en": "This is a medical condition and it responds to treatment.",
        "advice_bn": "এটি একটি চিকিৎসাযোগ্য অবস্থা, লজ্জার কিছু নয়।",
    },
    # ------------------------------------------------------------------- ENT
    "pharyngitis": {
        "en": "Throat infection",
        "bn": "গলার সংক্রমণ",
        "specialty": "ENT",
        "required": ["sore_throat"],
        "supporting": {"sore_throat": 3.0, "fever": 1.2, "cough": 0.8},
        "prior": 1.3,
        "advice_en": "Warm salt-water gargles help. See a doctor if swallowing is hard.",
        "advice_bn": "কুসুম গরম লবণ পানিতে গার্গল করুন। ঢোক গিলতে কষ্ট হলে ডাক্তার দেখান।",
    },
    "otitis_media": {
        "en": "Middle ear infection",
        "bn": "কানের সংক্রমণ",
        "specialty": "ENT",
        "required": ["ear_pain"],
        "supporting": {"ear_pain": 3.0, "fever": 1.5},
        "prior": 1.1,
        "advice_en": "Needs examination. Do not put anything in the ear.",
        "advice_bn": "পরীক্ষা প্রয়োজন। কানে কিছু ঢোকাবেন না।",
    },
    # ------------------------------------------------------------ dermatology
    "skin_infection": {
        "en": "Skin infection or allergic reaction",
        "bn": "চর্মরোগ বা অ্যালার্জি",
        "specialty": "Dermatology",
        "required": [],
        "supporting": {
            "skin_rash": 2.5, "rash": 2.5, "itching": 2.5, "fever": 0.6,
        },
        "prior": 1.2,
        "advice_en": "Avoid scratching. See a dermatologist if it spreads.",
        "advice_bn": "চুলকাবেন না। ছড়িয়ে পড়লে চর্মরোগ বিশেষজ্ঞ দেখান।",
    },
    # ------------------------------------------------------------------ other
    "anaemia": {
        "en": "Possible anaemia",
        "bn": "সম্ভাব্য রক্তস্বল্পতা",
        "specialty": "Internal Medicine",
        "required": [],
        "supporting": {
            "fatigue": 2.0, "weakness": 2.0, "dizziness": 1.5,
            "shortness_of_breath": 1.0,
        },
        "excluding": ["fever", "high_fever"],
        "prior": 1.3,
        "advice_en": "A simple blood count will confirm. Common and treatable.",
        "advice_bn": "সাধারণ রক্ত পরীক্ষায় ধরা পড়ে। সহজে চিকিৎসাযোগ্য।",
    },
    "dental_infection": {
        "en": "Dental infection",
        "bn": "দাঁতের সংক্রমণ",
        "specialty": "Dentistry",
        "required": ["toothache"],
        "supporting": {"toothache": 3.0, "swelling": 1.5, "fever": 1.0},
        "prior": 1.2,
        "advice_en": "See a dentist. Untreated infection can spread.",
        "advice_bn": "দন্ত চিকিৎসক দেখান। চিকিৎসা না করলে সংক্রমণ ছড়াতে পারে।",
    },
    "conjunctivitis": {
        "en": "Eye infection",
        "bn": "চোখের সংক্রমণ",
        "specialty": "Ophthalmology",
        "required": ["eye_pain"],
        "supporting": {"eye_pain": 2.5, "itching": 1.5, "blurred_vision": 1.0},
        "prior": 1.0,
        "advice_en": "Highly contagious. Wash hands and do not share towels.",
        "advice_bn": "খুব ছোঁয়াচে। হাত ধুয়ে নিন, তোয়ালে ভাগ করবেন না।",
    },
    "envenomation": {
        "en": "Snake bite",
        "bn": "সাপের কামড়",
        "specialty": "Emergency Medicine",
        "required": ["snake_bite"],
        "supporting": {"snake_bite": 4.0, "swelling": 1.0, "weakness": 1.0},
        "prior": 1.0,
        "red_flag": True,
        "acuity": 1,
        "advice_en": "Keep the limb still and below heart level. Reach a hospital "
                     "with antivenom now. Do not cut or tie the wound.",
        "advice_bn": "আক্রান্ত অঙ্গ নাড়াবেন না, হৃদপিণ্ডের নিচে রাখুন। "
                     "এখনই অ্যান্টিভেনম আছে এমন হাসপাতালে যান। কাটবেন বা বাঁধবেন না।",
    },
    "animal_bite": {
        "en": "Animal bite - rabies risk",
        "bn": "পশুর কামড় - জলাতঙ্কের ঝুঁকি",
        "specialty": "Emergency Medicine",
        "required": ["dog_bite"],
        "supporting": {"dog_bite": 4.0, "swelling": 0.8},
        "prior": 1.0,
        "red_flag": True,
        "acuity": 2,
        "advice_en": "Wash the wound with soap and running water for 15 minutes, "
                     "then get a rabies vaccine today.",
        "advice_bn": "১৫ মিনিট সাবান ও চলমান পানিতে ক্ষত ধুয়ে ফেলুন, "
                     "তারপর আজই জলাতঙ্কের টিকা নিন।",
    },
    "burn_injury": {
        "en": "Burn injury",
        "bn": "পোড়া আঘাত",
        "specialty": "Emergency Medicine",
        "required": ["burn_injury"],
        "supporting": {"burn_injury": 4.0},
        "prior": 1.0,
        "red_flag": True,
        "acuity": 2,
        "advice_en": "Cool with running water for 20 minutes. Do not apply "
                     "toothpaste, oil or butter.",
        "advice_bn": "২০ মিনিট চলমান ঠান্ডা পানি ঢালুন। টুথপেস্ট, তেল বা "
                     "মাখন লাগাবেন না।",
    },
    "trauma": {
        "en": "Injury from an accident",
        "bn": "দুর্ঘটনাজনিত আঘাত",
        "specialty": "Emergency Medicine",
        "required": ["accident_injury"],
        "supporting": {
            "accident_injury": 3.5, "severe_bleeding": 2.0, "unconscious": 2.0,
        },
        "prior": 1.0,
        "red_flag": True,
        "acuity": 1,
        "advice_en": "Do not move the patient if a spine injury is possible.",
        "advice_bn": "মেরুদণ্ডে আঘাতের সম্ভাবনা থাকলে রোগীকে নড়াবেন না।",
    },
}


def all_specialties() -> set[str]:
    return {entry["specialty"] for entry in CONDITIONS.values()}
