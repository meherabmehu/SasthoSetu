# -*- coding: utf-8 -*-
"""Check whether the language model layer is configured and working.

    python scripts/check_llm.py

Reports what is configured, sends one real request, and shows exactly what the
model added over the deterministic rules. Use this to confirm a key works
before wondering why triage results look unchanged.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.ai.extraction import extract  # noqa: E402
from app.ai.llm_extraction import (  # noqa: E402
    _provider_config,
    extract_with_llm,
    is_enabled,
)

# Phrasings the lexicon alone does not recognise. If the model is working,
# these are exactly the cases it should rescue.
SAMPLES = [
    "বুকটা যেন কেউ চেপে ধরছে, ঘামতেছি",
    "শরীরটা ম্যাজম্যাজ করতেছে, খাইতে ইচ্ছা করে না",
    "matha ta ghurtese, chokhe ondhokar dekhi",
    "niswas nite parchi na thik moto",
]


def main() -> None:
    config = _provider_config()
    key = config["key"]

    print("SasthoSetu language model check")
    print("=" * 60)
    print(f"  endpoint : {config['url']}")
    print(f"  model    : {config['model']}")
    print(f"  api key  : {'set (' + key[:6] + '...)' if key else 'NOT SET'}")
    print()

    if not is_enabled():
        print("LLM_API_KEY is not set, so the platform is running on its")
        print("deterministic rules alone. Every feature still works; the")
        print("lexicon simply understands fewer colloquial phrasings.")
        print()
        print("To enable it, set LLM_API_KEY in backend/.env and restart")
        print("the API. See docs/LLM_SETUP.md for free providers.")
        return

    print("Sending one live request per sample...")
    print("(any provider error is printed in full below)")
    print()

    # Surface the client's own diagnostics rather than swallowing them: the
    # whole point of this tool is to show why a request failed.
    logging.basicConfig(level=logging.INFO, format="       %(message)s")

    worked = 0
    for note in SAMPLES:
        rule_only = extract(note).symptoms
        merged, provenance = extract_with_llm(note)

        status = "ok " if provenance["llm_used"] else "FAIL"
        if provenance["llm_used"]:
            worked += 1

        print(f"[{status}] {note}")
        print(f"        rules alone : {rule_only or 'nothing recognised'}")
        print(f"        model added : {provenance['llm_added_symptoms'] or 'nothing'}")
        print(f"        final       : {merged.symptoms or 'nothing recognised'}")
        print()

    print("=" * 60)
    if worked == len(SAMPLES):
        print(f"All {worked} requests succeeded. The layer is working.")
    elif worked:
        print(f"{worked} of {len(SAMPLES)} succeeded - the provider may be")
        print("rate limiting. Retry in a minute.")
    else:
        print("No request succeeded. Triage still works on rules alone.")
        print()
        print("Read the provider error printed above - it names the cause.")
        print()
        print("  HTTP 401  the key is wrong, incomplete, or not yet active")
        print("  HTTP 403  blocked before reaching the API, often by a CDN")
        print("  HTTP 404  LLM_API_URL must end in /chat/completions")
        print("  HTTP 429  free quota reached; it resets on a schedule")
        print()
        print("Check the current settings with:")
        print("  python scripts/set_llm_key.py --show")


if __name__ == "__main__":
    main()
