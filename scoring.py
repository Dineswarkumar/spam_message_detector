"""
scoring.py  Phase 2 — Hybrid risk scorer with full explainability
"""
from rules import analyze, RuleResult
from dataclasses import dataclass, field
from typing import List, Dict


@dataclass
class RiskReport:
    risk_score:    int
    status:        str
    ml_confidence: float
    rule_score:    int
    flags:         List[str]
    reasons:       List[str]
    breakdown:     Dict
    verdict:       str


def compute_risk(ml_confidence: float, text: str) -> RiskReport:
    rule_result = analyze(text)

    ml_component   = round(ml_confidence * 55)
    rule_component = rule_result.score
    risk_score     = min(100, ml_component + rule_component)

    if risk_score >= 65:
        status = "Fraud"
    elif risk_score >= 35:
        status = "Suspicious"
    else:
        status = "Safe"

    if status == "Fraud":
        verdict = "This message shows strong signs of fraud. Do NOT share any details or click any links."
    elif status == "Suspicious":
        verdict = "This message has suspicious elements. Verify the source before taking any action."
    else:
        verdict = "This message appears safe based on our analysis."

    return RiskReport(
        risk_score    = risk_score,
        status        = status,
        ml_confidence = round(float(ml_confidence), 4),
        rule_score    = rule_component,
        flags         = rule_result.flags,
        reasons       = rule_result.reasons,
        breakdown     = {"ml_component": ml_component, "rule_component": rule_component, "total": risk_score},
        verdict       = verdict,
    )
