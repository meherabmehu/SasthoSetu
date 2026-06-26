DISEASE_RULES = [

    {
        "name": "Possible Heart or Lung Emergency",
        "symptoms": [
            "chest pain",
            "shortness of breath",
            "বুকে ব্যথা",
            "শ্বাসকষ্ট"
        ],
        "match": "any",
        "severity": "EMERGENCY",
        "doctor": "Emergency Medicine",
        "recommendation":
            "Go to the nearest hospital immediately."
    },

    {
        "name": "Possible Dengue",
        "symptoms": [
            "fever",
            "body pain",
            "জ্বর",
            "শরীর ব্যথা"
        ],
        "match": "all",
        "severity": "SPECIALIST",
        "doctor": "Medicine Specialist",
        "recommendation":
            "Get a CBC test and consult a physician immediately."
    },

    {
        "name": "Viral Fever",
        "symptoms": [
            "fever",
            "জ্বর"
        ],
        "match": "any",
        "severity": "CONSULT_DOCTOR",
        "doctor": "General Physician",
        "recommendation":
            "Drink plenty of fluids and consult a doctor if fever persists."
    },

    {
        "name": "Common Cold",
        "symptoms": [
            "cough",
            "কাশি",
            "sore throat",
            "গলা ব্যথা"
        ],
        "match": "any",
        "severity": "SELF_CARE",
        "doctor": "General Physician",
        "recommendation":
            "Take rest, drink warm fluids and monitor your symptoms."
    },

    {
        "name": "Tension Headache",
        "symptoms": [
            "headache",
            "মাথা ব্যথা"
        ],
        "match": "any",
        "severity": "SELF_CARE",
        "doctor": "General Physician",
        "recommendation":
            "Rest well, stay hydrated and consult a doctor if pain continues."
    }

]