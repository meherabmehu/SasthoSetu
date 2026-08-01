# Enabling the language model layer (free)

The platform works fully without this. The model only helps it understand
colloquial phrasings the phrase table misses — "বুকটা যেন কেউ চেপে ধরছে"
instead of "বুকে ব্যথা". Every clinical decision still comes from the
deterministic rules.

**Recommended: Groq.** Free, no credit card, and fast enough that triage does
not feel delayed.

---

## Step 1 — Get a free key

1. Go to **https://console.groq.com**
2. Sign up with Google, GitHub or email. No credit card is asked for.
3. Open **API Keys** in the left sidebar.
4. Click **Create API Key**, give it any name, and copy the value.

The key begins with `gsk_`. Copy it immediately — the console will not show it
again.

Free limits are per model and reset daily. On `llama-3.1-8b-instant` that is
roughly 30 requests per minute and hundreds of thousands of tokens per day,
which is far more than a demo or a pilot needs. Check the current figures at
https://console.groq.com/docs/rate-limits.

---

## Step 2 — Set the key with one command

From the project root, with the virtual environment active:

**Windows**
```powershell
python scripts\set_llm_key.py gsk_your_actual_key_here
```

**macOS / Linux**
```bash
python3 scripts/set_llm_key.py gsk_your_actual_key_here
```

That is the whole step. No file to find, no line to edit.

The script writes to `backend/.env`, creating it from the template if needed,
and adding the language model settings if your file predates them. It works
out the endpoint and model from the key prefix, so a Groq key is never left
pointing at OpenAI. Running it again replaces the key rather than adding a
second line.

To check what is currently set, with the key masked:

```
python scripts/set_llm_key.py --show
```

To force a specific provider or model:

```
python scripts/set_llm_key.py YOUR_KEY --provider openrouter
python scripts/set_llm_key.py YOUR_KEY --model llama-3.3-70b-versatile
```

Recognised providers: `groq`, `openrouter`, `gemini`, `openai`, `ollama`.

<details>
<summary>If you would rather edit the file by hand</summary>

Open `backend/.env` and set these three lines. Note it is `.env`, not
`.env.example` — the example file is a template that updates overwrite.

```
LLM_API_KEY=gsk_your_actual_key_here
LLM_API_URL=https://api.groq.com/openai/v1/chat/completions
LLM_MODEL=llama-3.1-8b-instant
```

No quotes around the key and no spaces around the `=`.
</details>

---

## Step 3 — Check it works

From the project root, with the virtual environment active:

**Windows**
```powershell
python scripts\check_llm.py
```

**macOS / Linux**
```bash
python3 scripts/check_llm.py
```

A working setup prints:

```
[ok ] বুকটা যেন কেউ চেপে ধরছে, ঘামতেছি
        rules alone : nothing recognised
        model added : ['chest_pain', 'weakness']
        final       : ['chest_pain', 'weakness']

All 4 requests succeeded. The layer is working.
```

That first line is the point of the whole layer: a 52-year-old describing
crushing chest pain in ordinary Bangla went from **understood as nothing** to
routed to Cardiology.

---

## Step 4 — Restart the API

The key is read at startup, so a running server will not pick it up. Stop the
API window with `Ctrl+C` and start it again:

```
cd backend
uvicorn app.main:app --reload
```

Now run a symptom check with a colloquial phrase. Under the recognised symptoms
you should see **"আপনার লেখা থেকে অতিরিক্ত যা বোঝা গেছে"** listing what the
model contributed.

---

## Other free providers

Any OpenAI-compatible endpoint works. Only the three settings change.

| Provider | `LLM_API_URL` | A free model | Notes |
|---|---|---|---|
| **Groq** | `https://api.groq.com/openai/v1/chat/completions` | `llama-3.1-8b-instant` | Fastest. Recommended |
| **OpenRouter** | `https://openrouter.ai/api/v1/chat/completions` | `meta-llama/llama-3.3-70b-instruct:free` | Many models behind one key |
| **Google Gemini** | `https://generativelanguage.googleapis.com/v1beta/openai/chat/completions` | `gemini-2.0-flash` | Key from aistudio.google.com |
| **Ollama** (your own machine) | `http://localhost:11434/v1/chat/completions` | `llama3.1:8b` | No key needed, nothing leaves your laptop |

### Ollama, for privacy

Sending symptom descriptions to a third-party API has real data-protection
implications under the forthcoming Bangladesh Personal Data Protection Act. A
local model avoids that entirely — nothing leaves the machine.

```bash
# install from https://ollama.com, then
ollama pull llama3.1:8b
```

```
LLM_API_KEY=ollama
LLM_API_URL=http://localhost:11434/v1/chat/completions
LLM_MODEL=llama3.1:8b
```

`LLM_API_KEY` must be non-empty — the platform treats a blank key as "layer
disabled" — but Ollama ignores its value.

---

## If it does not work

Run `scripts/check_llm.py` first; it will usually name the problem.

**"LLM_API_KEY is not set"**
The file was not saved, or you edited `.env.example` instead of `.env`. Confirm
`backend/.env` exists and contains your key.

**Every request fails**
Start the API with `APP_DEBUG=true` to see the provider's own error in the log.

- `401` — the key is wrong or was not copied whole
- `404` — `LLM_API_URL` is wrong, most often missing `/chat/completions`
- `400` with a model name — `LLM_MODEL` is not served by this provider
- `429` — free quota exhausted; it resets daily

**Some requests fail**
Rate limiting. The free tier allows about 30 requests a minute. Wait a minute.

**Triage results look unchanged**
The API was not restarted after editing `.env`, or the phrase you tried was
already in the lexicon. Try `শরীরটা ম্যাজম্যাজ করতেছে`, which the rules alone
cannot read.

---

## What the model is and is not allowed to do

Worth being clear about, because this is a health platform.

**It may:** read a description and say which known symptoms it mentions.

**It may not:**

- decide urgency, name a condition, or give advice
- remove a symptom the rules already matched — it cannot talk the system out
  of a red flag
- introduce a symptom outside the fixed vocabulary
- prevent a result when it is slow, broken or unreachable

If the provider is down, out of quota or misconfigured, triage silently falls
back to the rules and the patient still gets a full assessment. This is covered
by 20 automated tests, several of which feed the merge step deliberately
hostile output and assert the rules still win.
