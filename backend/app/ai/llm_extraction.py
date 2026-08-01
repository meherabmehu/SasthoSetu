# -*- coding: utf-8 -*-
"""LLM-assisted symptom understanding, bounded by the deterministic engine.

Why this layer exists
---------------------
The lexicon matches surface forms. Real patients do not write surface forms.
They write "বুকটা যেন কেউ চেপে ধরছে" (my chest feels like someone is crushing
it) or "শরীরটা ম্যাজম্যাজ করতেছে" (my body feels listless), and a phrase table
large enough to cover regional Bangladeshi speech would be unmaintainable.
A language model is genuinely good at this normalisation task.

Why it is not allowed to diagnose
---------------------------------
A hallucinated condition in a triage result is a safety failure, and a model
cannot show which symptom drove which conclusion. So the LLM is confined to one
job: mapping free text onto the **existing canonical symptom vocabulary**. It
returns symptom identifiers, never severities, conditions or advice. Everything
downstream — red flags, urgency, differential, referral — runs unchanged on
those identifiers.

The safety contract, in order of precedence:

1. **The lexicon always wins additively.** Anything the deterministic extractor
   found is kept. The model can only add symptoms, never remove them, so it
   cannot talk the system out of a red flag it already saw.
2. **Output is validated against the known vocabulary.** An identifier that is
   not already in SYMPTOMS is discarded. The model cannot invent a symptom.
3. **Failure is silent and safe.** No key, no network, bad JSON, timeout — the
   caller transparently receives the deterministic result. The platform never
   depends on the model being reachable.
4. **Nothing is escalated on the model's word alone.** Added symptoms flow into
   the same red-flag rules; the rules decide, not the model.
"""
from __future__ import annotations

import json
import logging
import os
import re
import urllib.error
import urllib.request
from dataclasses import replace
from typing import Optional

# Importing the settings module loads backend/.env into the environment.
# Without this the values read below come only from the shell, so a key set in
# the file would be silently ignored.
from app.core import config as _config  # noqa: F401

from .extraction import ExtractionResult, extract
from .lexicon import SYMPTOMS

logger = logging.getLogger("sasthosetu.llm")

# Sent on every request. Providers fronted by a CDN commonly reject the
# default Python user agent as suspected automated traffic.
USER_AGENT = "SasthoSetu/1.0 (+https://sasthosetu.gov.bd)"

# Kept short: triage is a foreground request and a patient describing chest
# pain must not wait on a slow model. On timeout we fall back to rules.
REQUEST_TIMEOUT_SECONDS = 6.0

# Only these fields are accepted back. Anything else in the response is ignored.
ALLOWED_KEYS = {"symptoms", "duration_days", "age", "qualifier", "negated"}

QUALIFIERS = {"severe", "mild", "intermittent"}


def _vocabulary() -> str:
    """The closed symptom list, grouped by body system.

    A flat alphabetical list of 57 identifiers is hard for a small model to
    search reliably: it tends to settle on a familiar-looking neighbour rather
    than the right one. Grouping by system, with the English gloss attached,
    measurably reduces confusions such as breathlessness being reported as
    chest pain.
    """
    groups: dict[str, list[str]] = {}
    for name, entry in sorted(SYMPTOMS.items()):
        gloss = entry["en"][0] if entry.get("en") else name.replace("_", " ")
        groups.setdefault(entry["specialty"], []).append(f"{name} ({gloss})")

    return "\n".join(
        f"  {specialty}: {', '.join(items)}"
        for specialty, items in sorted(groups.items())
    )


SYSTEM_PROMPT = """You are a clinical text normaliser for a Bangladeshi health \
platform. You do NOT diagnose, assess severity, or give advice.

Your only task: read a patient's description in Bangla, romanised Banglish, \
English or a mix, and map it onto a fixed list of symptom identifiers.

Rules:
- Choose ONLY from the allowed identifier list. Never invent an identifier.
- Map meaning, not words, and list EVERY symptom mentioned - not just one.
- Pick the identifier that matches the body part and sensation described. Do \
not substitute a nearby one: breathing difficulty is not chest pain, and \
dizziness is not headache.
- If the patient says a symptom is ABSENT, put it in "negated", not "symptoms".
- Report only what the patient states. Never infer a symptom that would merely \
be consistent with an illness you suspect.
- Return duration in days and age in years if stated, otherwise null.
- Respond with JSON only. No explanation, no markdown fence.

Worked examples:

"বুকটা যেন কেউ চেপে ধরছে, ঘামতেছি" (chest feels crushed, sweating)
{"symptoms": ["chest_pain", "weakness"], "negated": [], "duration_days": null, \
"age": null, "qualifier": null}

"niswas nite parchi na thik moto" (cannot breathe properly)
{"symptoms": ["shortness_of_breath"], "negated": [], "duration_days": null, \
"age": null, "qualifier": null}

"matha ta ghurtese, chokhe ondhokar dekhi" (head spinning, vision going dark)
{"symptoms": ["dizziness", "blurred_vision"], "negated": [], \
"duration_days": null, "age": null, "qualifier": null}

"শরীরটা ম্যাজম্যাজ করতেছে, খাইতে ইচ্ছা করে না" (body listless, no appetite)
{"symptoms": ["fatigue", "weakness"], "negated": [], "duration_days": null, \
"age": null, "qualifier": null}

"তিন দিন ধরে জ্বর আছে কিন্তু কাশি নেই" (fever three days, no cough)
{"symptoms": ["fever"], "negated": ["cough"], "duration_days": 3, \
"age": null, "qualifier": null}

Response shape:
{"symptoms": ["..."], "negated": ["..."], "duration_days": null, \
"age": null, "qualifier": null}

qualifier must be one of: severe, mild, intermittent, or null."""


def is_enabled() -> bool:
    return bool(os.environ.get("LLM_API_KEY"))


def _provider_config() -> dict:
    """Endpoint configuration.

    Defaults to the OpenAI-compatible chat completions shape, which most
    providers and local servers (Ollama, vLLM, LM Studio) also expose, so
    switching provider is a configuration change rather than a code change.
    """
    return {
        # Groq by default: it has a genuinely free tier and no card
        # requirement, which matters for a project deployed on a shoestring.
        "url": os.environ.get(
            "LLM_API_URL", "https://api.groq.com/openai/v1/chat/completions"
        ),
        "key": os.environ.get("LLM_API_KEY", ""),
        "model": os.environ.get("LLM_MODEL", "llama-3.1-8b-instant"),
    }


def _explain(error: urllib.error.HTTPError) -> str:
    """Turn a provider error into something the reader can act on.

    A bare status code sends people hunting for the wrong problem: a 403 from a
    CDN and a 401 from the API look equally like "bad key" but need completely
    different fixes.
    """
    try:
        detail = error.read().decode("utf-8", errors="replace")[:200]
    except Exception:  # noqa: BLE001 - diagnostics must not raise
        detail = ""

    hints = {
        401: "the API key is wrong, incomplete, or not yet active",
        403: (
            "the provider refused the request. If the body mentions error 1010 "
            "the request was blocked before reaching the API, usually by a CDN"
        ),
        404: "LLM_API_URL is wrong - it must end in /chat/completions",
        429: "free quota or rate limit reached - it resets on the provider's schedule",
    }
    hint = hints.get(error.code, "")

    parts = [f"HTTP {error.code}"]
    if hint:
        parts.append(hint)
    if detail.strip():
        parts.append(f"provider said: {detail.strip()}")
    return " | ".join(parts)


def _post(url: str, key: str, payload: dict) -> dict:
    """Send one request and return the decoded body."""
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {key}",
            # A User-Agent is mandatory in practice. urllib defaults to
            # "Python-urllib/3.x", which Groq's edge layer rejects outright
            # with a 403 (error 1010) before the request ever reaches the API,
            # producing a failure that looks exactly like a bad key.
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
            # Some gateways require these; harmless elsewhere.
            "HTTP-Referer": "https://sasthosetu.gov.bd",
            "X-Title": "SasthoSetu",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
        return json.loads(response.read().decode("utf-8"))


def _call_model(text: str) -> Optional[dict]:
    """Ask the model to normalise the note. Returns None on any failure."""
    config = _provider_config()
    if not config["key"]:
        return None

    payload = {
        "model": config["model"],
        "temperature": 0,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Allowed identifiers: {_vocabulary()}\n\n"
                    f"Patient description: {text}"
                ),
            },
        ],
    }

    # JSON mode improves reliability but is not universally supported: several
    # free and self-hosted endpoints reject the field outright. Ask for it,
    # then retry without it rather than losing the model entirely.
    attempts = [
        {**payload, "response_format": {"type": "json_object"}},
        payload,
    ]

    for index, attempt in enumerate(attempts):
        try:
            body = _post(config["url"], config["key"], attempt)
            content = body["choices"][0]["message"]["content"]
            return _parse_json(content)
        except urllib.error.HTTPError as error:
            # A 400 on the first attempt usually means the provider does not
            # know response_format, so the plain retry is worth making.
            if index == 0 and error.code in (400, 404, 422):
                logger.info("Provider rejected JSON mode, retrying without it")
                continue
            logger.warning(
                "LLM request failed, using rules only: %s", _explain(error)
            )
            return None
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            logger.warning("LLM request failed, using rules only: %s", error)
            return None
        except (KeyError, IndexError, ValueError) as error:
            logger.warning("LLM response unusable, using rules only: %s", error)
            return None
    return None


def _parse_json(content: str) -> Optional[dict]:
    """Parse the model's reply, tolerating a stray markdown fence."""
    content = content.strip()
    if content.startswith("```"):
        content = re.sub(r"^```[a-z]*\n?|\n?```$", "", content).strip()
    try:
        parsed = json.loads(content)
    except ValueError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _validated_symptoms(values) -> list[str]:
    """Keep only identifiers that already exist in the lexicon."""
    if not isinstance(values, list):
        return []
    seen = []
    for value in values:
        if not isinstance(value, str):
            continue
        key = value.strip().lower().replace(" ", "_").replace("-", "_")
        if key in SYMPTOMS and key not in seen:
            seen.append(key)
    return seen


def _validated_int(value, low: int, high: int) -> Optional[int]:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if low <= number <= high else None


# Phrases whose meaning is unambiguous enough to assert directly. The model is
# good at paraphrase but an 8B model occasionally picks a plausible neighbour
# instead of the right identifier - breathlessness reported as chest pain, for
# instance, which sends a respiratory patient to Cardiology. Where a phrase
# admits only one reading, the rules settle it rather than the model.
# Each entry: phrases, the symptom they state, and the symptoms a model is
# known to confuse them with. The confusions are displaced, because leaving the
# wrong reading in place alongside the right one can fabricate a combination
# neither the patient nor the model reported - breathlessness misread as chest
# pain, then joined by the corrected breathlessness, becomes a false cardiac
# emergency.
DECISIVE_PHRASES = [
    (("niswas nite parchi na", "nishwas nite parchi na", "শ্বাস নিতে পারছি না",
      "নিঃশ্বাস নিতে পারছি না", "dom nite parchi na", "দম নিতে পারছি না"),
     "shortness_of_breath", ("chest_pain",)),
    (("matha ghurtese", "matha ghurche", "মাথা ঘুরতেছে", "মাথা ঘুরছে",
      "matha ta ghurtese"), "dizziness", ("headache",)),
    (("chokhe ondhokar", "চোখে অন্ধকার"), "blurred_vision", ()),
    (("khaite icche kore na", "খাইতে ইচ্ছা করে না", "খেতে ইচ্ছে করে না"),
     "fatigue", ()),
]


def _decisive_symptoms(text: str) -> tuple[list[str], set[str]]:
    """Symptoms a phrase states plainly, and the misreadings they displace."""
    lowered = (text or "").lower()
    found: list[str] = []
    displaced: set[str] = set()

    for phrases, symptom, confusions in DECISIVE_PHRASES:
        if symptom in SYMPTOMS and any(p in lowered for p in phrases):
            if symptom not in found:
                found.append(symptom)
            displaced.update(confusions)

    # Never displace something the phrase itself asserts.
    return found, displaced - set(found)


def merge(base: ExtractionResult, model_output: dict) -> ExtractionResult:
    """Combine the model's reading with the deterministic result.

    Additive by construction. A symptom the lexicon matched stays matched
    whatever the model says, because the lexicon is the auditable component and
    the model is the assistive one.
    """
    added = _validated_symptoms(model_output.get("symptoms"))
    model_negated = _validated_symptoms(model_output.get("negated"))

    symptoms = list(base.symptoms)
    for name in added:
        # Never re-add something the rules explicitly saw as denied: "জ্বর নেই"
        # is a clearer signal than a model's guess.
        if name not in symptoms and name not in base.negated_symptoms:
            symptoms.append(name)

    negated = list(base.negated_symptoms)
    for name in model_negated:
        # A model-reported negation may not remove a symptom the rules found.
        # Dropping a red flag on the model's word is the one thing this layer
        # must never do.
        if name not in negated and name not in base.symptoms:
            negated.append(name)

    duration = base.duration_days
    if duration is None:
        duration = _validated_int(model_output.get("duration_days"), 0, 3650)

    age = base.age
    if age is None:
        age = _validated_int(model_output.get("age"), 0, 120)

    qualifier = base.qualifier
    if qualifier is None:
        candidate = model_output.get("qualifier")
        if isinstance(candidate, str) and candidate.lower() in QUALIFIERS:
            qualifier = candidate.lower()

    return replace(
        base,
        symptoms=symptoms,
        negated_symptoms=negated,
        duration_days=duration,
        age=age,
        qualifier=qualifier,
    )


def extract_with_llm(text: str) -> tuple[ExtractionResult, dict]:
    """Extract entities, using the model to catch what the lexicon missed.

    Returns the result plus provenance describing what each layer contributed,
    so a clinician reviewing a case can see whether a symptom came from an
    auditable rule or from a model.
    """
    base = extract(text or "")

    provenance = {
        "llm_used": False,
        "llm_available": is_enabled(),
        "rule_symptoms": list(base.symptoms),
        "llm_added_symptoms": [],
    }

    if not is_enabled():
        return base, provenance

    model_output = _call_model(text or "")
    if not model_output:
        # Deliberately silent: the patient still gets a full rules-based
        # assessment, which is the whole point of the fallback.
        return base, provenance

    merged = merge(base, model_output)

    # A decisive phrase overrides a model that read it differently.
    decisive, displaced = _decisive_symptoms(text)
    for symptom in decisive:
        if symptom not in merged.symptoms and symptom not in merged.negated_symptoms:
            merged.symptoms.append(symptom)

    # Drop the model's misreading, but only if the rules did not independently
    # find it. A lexicon match is evidence; a model guess it contradicts is not.
    for symptom in displaced:
        if symptom in merged.symptoms and symptom not in base.symptoms:
            merged.symptoms.remove(symptom)

    provenance["llm_used"] = True
    provenance["llm_added_symptoms"] = [
        name for name in merged.symptoms if name not in base.symptoms
    ]
    return merged, provenance
