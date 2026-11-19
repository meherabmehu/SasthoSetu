# AI-native safety architecture

SasthoSetu intentionally uses several AI techniques, but none may bypass the
deterministic emergency-safety layer.

```mermaid
flowchart LR
  I[Bangla / Banglish / English input] --> L[LLM constrained symptom normalisation]
  I --> X[Deterministic lexicon extraction]
  L --> V[Closed-vocabulary validation]
  X --> G[Safety pathway graph]
  V --> G
  G --> R[Red-flag rules: escalation only]
  R --> M[Calibrated ML triage confidence]
  M --> Q[RAG: WHO primary-source retrieval]
  Q --> H[Human clinician handoff / consented record]
```

- **LLM:** only maps free text to the existing symptom vocabulary. PII is
  redacted, provider hosts are allowlisted, and failures fall back to rules.
- **Graph:** the care pathway is a directed safety graph: input -> extraction
  -> red flags -> triage -> evidence -> clinician handoff. A later layer may
  never lower an emergency escalation made by an earlier safety node.
- **ML:** the trained triage classifier and research image models provide
  bounded support, confidence bands and low-confidence review prompts.
- **RAG:** retrieval returns curated WHO source cards relevant to red flags or
  dengue/arboviral symptoms. It does not generate prescriptions or diagnoses.

Every production claim must preserve this distinction: AI assists navigation
and screening; it does not autonomously diagnose or replace a clinician.
