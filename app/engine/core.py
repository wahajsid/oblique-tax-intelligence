"""Shared building blocks for every calculator.

Design principles (non-negotiable):
- A deterministic rules engine performs the calculation; AI may only explain it.
- Arithmetic is done in ``decimal.Decimal`` and rounded half-up to the currency's
  minor unit (2 places for AED/SAR/QAR, 3 for BHD/OMR/KWD).
- Every result carries a working-paper trace, the rule ids used, each rule's review
  status and source, and an ``outcome`` that says whether the figure may be relied
  on as an illustrative estimate or still needs scope confirmation.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

RULES_DIR = Path(__file__).resolve().parent.parent / "rules"

ReviewStatus = Literal["verified", "verified_secondary", "pending_verification", "draft_law"]
Outcome = Literal["ILLUSTRATIVE_ESTIMATE", "REVIEW_REQUIRED"]
Answer = Literal["no", "yes", "unknown"]

# Minor-unit precision per ISO 4217 currency. Anything not listed uses 2.
CURRENCY_DECIMALS: dict[str, int] = {
    "BHD": 3, "OMR": 3, "KWD": 3, "JOD": 3,
    "AED": 2, "SAR": 2, "QAR": 2, "USD": 2, "GBP": 2, "EUR": 2, "INR": 2, "SGD": 2,
    "HKD": 2, "AUD": 2, "ZAR": 2, "PKR": 2, "CAD": 2,
}

ZERO = Decimal("0")


def D(value: Any) -> Decimal:
    """Convert ints, floats, strings or Decimals to Decimal without binary-float noise."""
    if isinstance(value, Decimal):
        return value
    if value is None:
        return ZERO
    return Decimal(str(value))


def decimals_for(currency: str) -> int:
    return CURRENCY_DECIMALS.get(currency.upper(), 2)


def money(value: Any, currency: str | None = None, places: int | None = None) -> float:
    """Round half-up to the currency's minor unit (or explicit places) and return a float
    for JSON. The *computation* stays in Decimal; only the presentation value is a float."""
    if places is None:
        places = decimals_for(currency) if currency else 2
    q = Decimal(1).scaleb(-places)
    return float(D(value).quantize(q, rounding=ROUND_HALF_UP))


def ratio(numerator: Any, denominator: Any, places: int = 4) -> float | None:
    den = D(denominator)
    if den == 0:
        return None
    return float((D(numerator) / den).quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP))


@lru_cache(maxsize=None)
def load_rules(jurisdiction: str) -> dict[str, Any]:
    """Load and cache the JSON ruleset for a jurisdiction code such as 'ae'."""
    path = RULES_DIR / f"{jurisdiction.lower()}.json"
    if not path.exists():
        raise FileNotFoundError(f"No ruleset for jurisdiction '{jurisdiction}'")
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def rule(jurisdiction: str, *path: str) -> dict[str, Any]:
    """Fetch one rule dict, e.g. rule('ae', 'corporate_tax', 'standard_rate')."""
    node: Any = load_rules(jurisdiction)["rules"]
    for key in path:
        node = node[key]
    return node


def param(r: dict[str, Any], key: str) -> Decimal:
    """Decimal view of a numeric rule parameter."""
    return D(r["parameters"][key])


@lru_cache(maxsize=None)
def rule_index() -> dict[str, dict[str, Any]]:
    """Map every rule_id across all rule files to its rule dict."""
    idx: dict[str, dict[str, Any]] = {}
    for path in RULES_DIR.glob("*.json"):
        with path.open(encoding="utf-8") as fh:
            data = json.load(fh)
        groups: list[dict[str, Any]] = []
        if "rules" in data and isinstance(data["rules"], dict):
            groups += [g for g in data["rules"].values() if isinstance(g, dict)]
        for c in data.get("countries", {}).values():
            if isinstance(c, dict) and isinstance(c.get("rules"), dict):
                groups.append(c["rules"])
        if isinstance(data.get("uae"), dict):
            groups.append(data["uae"])
        for g in groups:
            for r in g.values():
                if isinstance(r, dict) and r.get("rule_id"):
                    idx[r["rule_id"]] = r
    return idx


def find_rule(rule_id: str) -> dict[str, Any] | None:
    return rule_index().get(rule_id)


@dataclass
class TraceStep:
    """One line of the calculation working paper."""
    label: str
    amount: float | None = None
    formula: str | None = None
    rule_id: str | None = None
    note: str | None = None
    kind: Literal["input", "adjustment", "subtotal", "tax", "info", "warning"] = "adjustment"

    def as_dict(self) -> dict[str, Any]:
        return {k: v for k, v in self.__dict__.items() if v is not None}


@dataclass
class Flag:
    """A diagnostic finding: an unresolved question or a risk worth a human look."""
    code: str
    severity: Literal["info", "attention", "high"]
    title: str
    detail: str
    advisory_hook: str | None = None  # what Oblique can help with

    def as_dict(self) -> dict[str, Any]:
        return {k: v for k, v in self.__dict__.items() if v is not None}


@dataclass
class CalculationResult:
    calculator: str
    jurisdiction: str
    currency: str
    ruleset_version: str
    inputs: dict[str, Any]
    outputs: dict[str, Any]
    trace: list[TraceStep] = field(default_factory=list)
    flags: list[Flag] = field(default_factory=list)
    rules_used: list[str] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    outcome: Outcome = "ILLUSTRATIVE_ESTIMATE"
    review_reasons: list[str] = field(default_factory=list)

    # ---- building ----------------------------------------------------------------
    def add(self, step: TraceStep) -> None:
        self.trace.append(step)
        if step.rule_id and step.rule_id not in self.rules_used:
            self.rules_used.append(step.rule_id)

    def flag(self, f: Flag) -> None:
        self.flags.append(f)

    def m(self, value: Any) -> float:
        """Round to this result's currency precision."""
        return money(value, self.currency)

    def apply_scope_gate(self, scope_confirmed: bool, special_regime: Answer, excluded: str) -> None:
        """V4-style gate. We still compute the figure (so the visitor sees the order of
        magnitude) but mark the outcome REVIEW_REQUIRED and say why, and the UI greys it."""
        reasons: list[str] = []
        if not scope_confirmed:
            reasons.append("You have not confirmed that your facts fit the stated scope of this calculator.")
        if special_regime == "yes":
            reasons.append("You indicated that a special regime, exemption or relief may apply. Those change the answer and are not fully modelled here.")
        elif special_regime == "unknown":
            reasons.append("You are not sure whether a special regime, exemption or relief applies. Eligibility must be established before the figure is relied on.")
        if reasons or self.review_reasons:
            self.outcome = "REVIEW_REQUIRED"
            self.review_reasons = self.review_reasons + reasons + [f"Outside the scope of this calculator: {excluded}"]
            if reasons:
                self.flag(Flag("review_required", "high", "Review required before relying on this figure",
                               " ".join(reasons), "Oblique will confirm scope, eligibility and the applicable regime for your facts."))

    # ---- metadata ------------------------------------------------------------------
    def rule_metadata(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for rid in self.rules_used:
            r = find_rule(rid)
            if r:
                out.append({
                    "rule_id": rid,
                    "description": r.get("description"),
                    "review_status": r.get("review_status"),
                    "source_reference": r.get("source_reference"),
                    "source_url": r.get("source_url"),
                    "effective_from": r.get("effective_from"),
                    "effective_to": r.get("effective_to"),
                    "verification_note": r.get("verification_note"),
                })
        return out

    def review_status(self) -> str:
        order = ["verified", "verified_secondary", "pending_verification", "draft_law"]
        worst = 0
        for meta in self.rule_metadata():
            worst = max(worst, order.index(meta.get("review_status", "pending_verification")))
        return order[worst]

    def as_dict(self) -> dict[str, Any]:
        return {
            "calculator": self.calculator,
            "jurisdiction": self.jurisdiction,
            "currency": self.currency,
            "currency_decimals": decimals_for(self.currency),
            "ruleset_version": self.ruleset_version,
            "outcome": self.outcome,
            "review_reasons": self.review_reasons,
            "review_status": self.review_status(),
            "inputs": self.inputs,
            "outputs": self.outputs,
            "trace": [s.as_dict() for s in self.trace],
            "flags": [f.as_dict() for f in self.flags],
            "assumptions": self.assumptions,
            "rules": self.rule_metadata(),
            "disclaimer": DISCLAIMER,
            "persisted": False,
        }


DISCLAIMER = (
    "A desktop estimate from your inputs and the rules shown. Not advice. "
    "For your numbers, talk to Oblique Consult. Your inputs are not stored."
)
