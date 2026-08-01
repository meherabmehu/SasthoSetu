# -*- coding: utf-8 -*-
"""Set the language model API key without hand-editing any file.

    python scripts/set_llm_key.py gsk_your_key_here

Handles the cases that make manual editing error-prone:

* creates ``backend/.env`` from the template if it is missing
* adds the LLM settings if the file predates them, rather than silently
  changing nothing
* replaces an existing key rather than appending a second one, since a
  duplicate line would quietly win or lose depending on parse order
* infers the endpoint and model from the key prefix, so a Groq key does not
  end up pointed at OpenAI
* strips quotes and stray whitespace people paste in by accident

Pass ``--provider`` to override the inferred endpoint, or ``--show`` to print
the current settings with the key masked.
"""
from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / "backend" / ".env"
TEMPLATE = ROOT / "backend" / ".env.example"

PROVIDERS = {
    "groq": {
        "url": "https://api.groq.com/openai/v1/chat/completions",
        "model": "llama-3.1-8b-instant",
        "label": "Groq",
    },
    "openrouter": {
        "url": "https://openrouter.ai/api/v1/chat/completions",
        "model": "meta-llama/llama-3.3-70b-instruct:free",
        "label": "OpenRouter",
    },
    "gemini": {
        "url": (
            "https://generativelanguage.googleapis.com/v1beta/openai/"
            "chat/completions"
        ),
        "model": "gemini-2.0-flash",
        "label": "Google Gemini",
    },
    "openai": {
        "url": "https://api.openai.com/v1/chat/completions",
        "model": "gpt-4o-mini",
        "label": "OpenAI",
    },
    "ollama": {
        "url": "http://localhost:11434/v1/chat/completions",
        "model": "llama3.1:8b",
        "label": "Ollama (local)",
    },
}

# Key prefixes are distinctive enough to pick the right endpoint automatically,
# which removes the most common misconfiguration: a Groq key aimed at OpenAI.
PREFIX_HINTS = [
    ("gsk_", "groq"),
    ("sk-or-", "openrouter"),
    ("sk-proj-", "openai"),
    ("sk-", "openai"),
    ("AIza", "gemini"),
]

SETTINGS_BLOCK = """
# Language model for symptom understanding (optional).
# Managed by scripts/set_llm_key.py - see docs/LLM_SETUP.md
LLM_API_KEY={key}
LLM_API_URL={url}
LLM_MODEL={model}
"""


def detect_provider(key: str) -> str:
    for prefix, name in PREFIX_HINTS:
        if key.startswith(prefix):
            return name
    return "groq"


def clean(value: str) -> str:
    """Remove quotes and whitespace a paste often carries along."""
    return value.strip().strip('"').strip("'").strip()


def ensure_env_file() -> None:
    if ENV_FILE.exists():
        return
    if not TEMPLATE.exists():
        raise SystemExit(
            f"Neither {ENV_FILE} nor {TEMPLATE} exists. Run this from the "
            "project root after cloning."
        )
    shutil.copy2(TEMPLATE, ENV_FILE)
    print(f"Created {ENV_FILE.relative_to(ROOT)} from the template.")


def set_value(text: str, name: str, value: str) -> tuple[str, bool]:
    """Replace a setting in place. Returns the text and whether it was found."""
    pattern = re.compile(rf"^{name}=.*$", re.MULTILINE)
    if pattern.search(text):
        return pattern.sub(f"{name}={value}", text, count=1), True
    return text, False


def show_current() -> None:
    if not ENV_FILE.exists():
        print(f"{ENV_FILE.relative_to(ROOT)} does not exist yet.")
        return

    text = ENV_FILE.read_text(encoding="utf-8")
    print(f"Settings in {ENV_FILE.relative_to(ROOT)}:")
    found = False
    for name in ("LLM_API_KEY", "LLM_API_URL", "LLM_MODEL"):
        match = re.search(rf"^{name}=(.*)$", text, re.MULTILINE)
        if not match:
            continue
        found = True
        value = match.group(1).strip()
        if name == "LLM_API_KEY" and value:
            value = f"{value[:7]}...{value[-4:]}" if len(value) > 12 else "set"
        print(f"  {name} = {value or '(empty)'}")

    if not found:
        print("  none - this file predates the language model settings.")
        print("  Run this script with a key to add them.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Set the language model API key in backend/.env"
    )
    parser.add_argument("key", nargs="?", help="your API key")
    parser.add_argument(
        "--provider",
        choices=sorted(PROVIDERS),
        help="override the provider inferred from the key",
    )
    parser.add_argument("--model", help="override the model name")
    parser.add_argument(
        "--show", action="store_true", help="print current settings and exit"
    )
    arguments = parser.parse_args()

    if arguments.show:
        show_current()
        return

    if not arguments.key:
        parser.print_help()
        print()
        show_current()
        sys.exit(1)

    key = clean(arguments.key)
    if not key:
        raise SystemExit("The key is empty after removing quotes and spaces.")

    provider_name = arguments.provider or detect_provider(key)
    provider = PROVIDERS[provider_name]
    model = arguments.model or provider["model"]

    ensure_env_file()
    text = ENV_FILE.read_text(encoding="utf-8")

    text, had_key = set_value(text, "LLM_API_KEY", key)
    text, _ = set_value(text, "LLM_API_URL", provider["url"])
    text, _ = set_value(text, "LLM_MODEL", model)

    if not had_key:
        # An older .env has no LLM lines at all. Append them rather than
        # reporting success while changing nothing.
        text = text.rstrip("\n") + "\n" + SETTINGS_BLOCK.format(
            key=key, url=provider["url"], model=model
        )
        print("This .env predated the language model settings, so they were added.")

    ENV_FILE.write_text(text, encoding="utf-8")

    print()
    print(f"  file     : {ENV_FILE.relative_to(ROOT)}")
    print(f"  provider : {provider['label']}")
    print(f"  model    : {model}")
    print(f"  key      : {key[:7]}...{key[-4:]}" if len(key) > 12 else "  key set")
    print()
    print("Next:")
    print("  1. python scripts/check_llm.py     verify the key works")
    print("  2. restart the API                 it reads the key at startup")


if __name__ == "__main__":
    main()
