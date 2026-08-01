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

from .extraction import ExtractionResult, extract
from .lexicon import SYMPTOMS

logger = logging.getLogger("sasthosetu.llm")

# Kept short: triage is a foreground request and a patient describing chest
# pain must not wait on a slow model. On timeout we fall back to rules.
REQUEST_TIMEOUT_SECONDS = 6.0

# Only these fields are accepted back. Anything else in the response is ignored.
ALLOWED_KEYS = {"symptoms", "duration_days", "age", "qualifier", "negated"}

QUALIFIERS = {"severe", "mild", "intermittent"}


def _vocabulary() -> str:
    """The closed symptom list the model is permitted to choose from."""
    return ", ".join(sorted(SYMPTOMS))


SYSTEM_PROMPT = """You are a clinical text normaliser for a Bangladeshi health \
platform. You do NOT diagnose, assess severity, or give advice.

Your only task: read a patient's description in Bangla, romanised Banglish, \
English or a mix, and map it onto a fixed list of symptom identifiers.

Rules you must follow:
- Choose ONLY from the allowed identifier list. Never invent an identifier.
- Map meaning, not words. "বুকটা কেউ চেপে ধরছে" means chest_pain. \
"শ্বাস নিতে পারছি না" means shortness_of_breath.
- If the patient says a symptom is ABSENT, put it in "negated", not "symptoms".
- Include a symptom only if the patient actually reports it. Do not infer \
symptoms that would merely be consistent with a suspected illness.
- Return duration in days if stated, age in years if stated, otherwise null.
- Respond with JSON only. No explanation, no markdown fence.

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
        "url": os.environ.get(
            "LLM_API_URL", "https://api.openai.com/v1/chat/completions"
        ),
        "key": os.environ.get("LLM_API_KEY", ""),
        "model": os.environ.get("LLM_MODEL", "gpt-4o-mini"),
    }


def _call_model(text: str) -> Optional[dict]:
    """Ask the model to normalise the note. Returns None on any failure."""
    config = _provider_config()
    if not config["key"]:
        return None

    payload = {
        "model": config["model"],
        "temperature": 0,
        "response_format": {"type": "json_object"},
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

    request = urllib.request.Request(
        config["url"],
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {config['key']}",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(
            request, timeout=REQUEST_TIMEOUT_SECONDS
        ) as response:
            body = json.loads(response.read().decode("utf-8"))
        content = body["choices"][0]["message"]["content"]
        return _parse_json(content)
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        logger.warning("LLM request failed, using rules only: %s", error)
        return None
    except (KeyError, IndexError, ValueError) as error:
        logger.warning("LLM response unusable, using rules only: %s", error)
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

    provenance["llm_used"] = True
    provenance["llm_added_symptoms"] = [
        name for name in merged.symptoms if name not in base.symptoms
    ]
    return merged, provenance
