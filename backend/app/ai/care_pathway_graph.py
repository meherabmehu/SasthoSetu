"""Explainable directed graph for the AI-assisted care pathway.

This is a safety graph, not a diagnostic knowledge graph: it makes the
decision path inspectable and guarantees that red-flag escalation precedes ML
confidence and RAG evidence retrieval.
"""
from __future__ import annotations


def build_care_pathway_graph(*, triage_level: str, safety_flags: list[str]) -> dict:
    emergency = bool(safety_flags) or triage_level == "EMERGENCY"
    route = "emergency_referral" if emergency else "clinician_or_self_care"
    nodes = [
        {"id": "input", "label": "Bangla/Banglish/English input", "kind": "input"},
        {"id": "normalise", "label": "Closed-vocabulary LLM + lexicon normalisation", "kind": "llm"},
        {"id": "safety", "label": "Deterministic red-flag safety rules", "kind": "safety"},
        {"id": "ml", "label": "Calibrated ML confidence", "kind": "ml"},
        {"id": "rag", "label": "WHO evidence retrieval", "kind": "rag"},
        {"id": route, "label": "Emergency referral" if emergency else "Care pathway and clinician handoff", "kind": "outcome"},
    ]
    return {
        "nodes": nodes,
        "edges": [
            ["input", "normalise"], ["normalise", "safety"], ["safety", "ml"],
            ["ml", "rag"], ["rag", route],
        ],
        "invariant": "The ML and RAG nodes may add explanation, never reduce a red-flag escalation.",
        "safety_flags": safety_flags,
    }
