"""
Risk Scorer — Weighted Safety Score Calculator

Calculates a 0-100 safety score based on verified findings.
Unlike a naive deduction model, this scorer accounts for:

  1. **Severity weight** — must_raise hits harder than worth_raising
  2. **Confidence weighting** — low-confidence findings penalize less
  3. **Diminishing returns** — the 10th finding hurts less than the 1st
  4. **Category diversity** — risks across many categories are worse
  5. **Verification quality** — findings with uncertain semantic checks score lower

Scoring Formula:
  - Base penalty per finding = severity_weight × confidence × diminishing_factor
  - Category diversity multiplier = 1 + 0.1 × (unique_categories - 1), capped at 1.5x
  - Total penalty = sum(all penalties) × diversity_multiplier
  - Final score = max(0, 100 - total_penalty)

Industry-grade: deterministic, explainable, and auditable.
"""

import math
from typing import Optional


# ── Configuration ────────────────────────────────────────────────────────────

# Base penalties per severity level (before confidence/diminishing adjustments)
SEVERITY_WEIGHTS = {
    "must_raise": 18,     # Serious risks: significant score impact
    "worth_raising": 7,   # Moderate risks: noticeable but not devastating
}

# Minimum confidence floor — findings below this confidence get reduced penalty
# (they might be hallucinated, so we don't let them tank the score)
MIN_CONFIDENCE_FOR_FULL_PENALTY = 0.7

# Diminishing returns: each successive finding in the SAME category hurts less
# Formula: penalty * (1 / (1 + 0.15 * count_in_category))
DIMINISHING_RETURNS_FACTOR = 0.15

# Category diversity multiplier: more diverse risks = worse score
# Each unique category beyond the first adds 10% to total penalty, capped at 1.5x
DIVERSITY_INCREMENT = 0.10
DIVERSITY_CAP = 1.5

# Semantic verification discount
# UNCERTAIN findings get a 30% penalty reduction (they might be false positives)
UNCERTAIN_DISCOUNT = 0.30


class RiskScorer:
    """
    Calculates a weighted safety score from verified findings.
    Returns a score from 0 (extremely risky) to 100 (completely safe).
    """

    def calculate_score(self, findings: list[dict]) -> tuple[int, dict]:
        """
        Calculate the safety score and return (score, breakdown_dict).
        The breakdown dict provides full audit trail of how the score was derived.
        """
        if not findings:
            return 100, {
                "total_penalty": 0,
                "findings_count": 0,
                "category_count": 0,
                "per_finding_penalties": [],
                "diversity_multiplier": 1.0,
            }

        # Track per-category finding counts for diminishing returns
        category_counts: dict[str, int] = {}
        per_finding_penalties = []

        for finding in findings:
            severity = finding.get("severity", "worth_raising").lower()
            confidence = self._get_confidence(finding)
            category = finding.get("category", "other_risk")
            semantic_check = finding.get("semantic_check", {})
            verdict = semantic_check.get("verdict", "").upper()

            # ── Step 1: Base penalty from severity ────────────────────────
            base_penalty = SEVERITY_WEIGHTS.get(severity, SEVERITY_WEIGHTS["worth_raising"])

            # ── Step 2: Confidence adjustment ─────────────────────────────
            # Full penalty at >= 0.7 confidence; linearly reduced below that
            if confidence >= MIN_CONFIDENCE_FOR_FULL_PENALTY:
                confidence_multiplier = 1.0
            else:
                # Scale from 0.3 (at confidence=0) to 1.0 (at confidence=0.7)
                confidence_multiplier = 0.3 + (confidence / MIN_CONFIDENCE_FOR_FULL_PENALTY) * 0.7

            # ── Step 3: Semantic verification discount ────────────────────
            semantic_discount = 1.0
            if verdict == "UNCERTAIN":
                semantic_discount = 1.0 - UNCERTAIN_DISCOUNT

            # ── Step 4: Diminishing returns per category ──────────────────
            count_in_category = category_counts.get(category, 0)
            diminishing = 1.0 / (1.0 + DIMINISHING_RETURNS_FACTOR * count_in_category)
            category_counts[category] = count_in_category + 1

            # ── Compute final per-finding penalty ─────────────────────────
            penalty = base_penalty * confidence_multiplier * semantic_discount * diminishing
            per_finding_penalties.append({
                "category": category,
                "severity": severity,
                "confidence": round(confidence, 2),
                "semantic_verdict": verdict or "N/A",
                "base_penalty": base_penalty,
                "confidence_multiplier": round(confidence_multiplier, 3),
                "semantic_discount": round(semantic_discount, 3),
                "diminishing_factor": round(diminishing, 3),
                "final_penalty": round(penalty, 2),
            })

        # ── Step 5: Category diversity multiplier ─────────────────────────
        unique_categories = len(category_counts)
        diversity_multiplier = min(
            1.0 + DIVERSITY_INCREMENT * max(0, unique_categories - 1),
            DIVERSITY_CAP
        )

        # ── Step 6: Final score ───────────────────────────────────────────
        total_penalty = sum(p["final_penalty"] for p in per_finding_penalties)
        total_penalty *= diversity_multiplier

        score = max(0, min(100, round(100 - total_penalty)))

        breakdown = {
            "total_penalty": round(total_penalty, 2),
            "findings_count": len(findings),
            "category_count": unique_categories,
            "diversity_multiplier": round(diversity_multiplier, 3),
            "per_finding_penalties": per_finding_penalties,
        }

        return score, breakdown

    def _get_confidence(self, finding: dict) -> float:
        """Safely extract confidence value."""
        try:
            return float(finding.get("confidence", 0.5))
        except (TypeError, ValueError):
            return 0.5


# ── Standalone Test ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    scorer = RiskScorer()

    # Test case 1: Empty findings
    score, breakdown = scorer.calculate_score([])
    print(f"Empty findings: score={score}, breakdown={breakdown}")

    # Test case 2: Single must_raise finding
    test_findings = [
        {
            "severity": "must_raise",
            "category": "ip_ownership",
            "confidence": 0.9,
            "semantic_check": {"verdict": "YES"}
        }
    ]
    score, breakdown = scorer.calculate_score(test_findings)
    print(f"\nSingle must_raise (0.9 conf): score={score}")
    print(f"  penalty={breakdown['total_penalty']}, diversity={breakdown['diversity_multiplier']}")

    # Test case 3: Multiple findings across categories
    test_findings_2 = [
        {"severity": "must_raise", "category": "ip_ownership", "confidence": 0.95, "semantic_check": {"verdict": "YES"}},
        {"severity": "must_raise", "category": "payment_terms", "confidence": 0.85, "semantic_check": {"verdict": "YES"}},
        {"severity": "worth_raising", "category": "kill_fee", "confidence": 0.6, "semantic_check": {"verdict": "UNCERTAIN"}},
        {"severity": "worth_raising", "category": "liability_cap", "confidence": 0.7, "semantic_check": {"verdict": "YES"}},
        {"severity": "must_raise", "category": "indemnification", "confidence": 0.8, "semantic_check": {"verdict": "YES"}},
    ]
    score, breakdown = scorer.calculate_score(test_findings_2)
    print(f"\n5 findings across 5 categories: score={score}")
    print(f"  penalty={breakdown['total_penalty']}, diversity={breakdown['diversity_multiplier']}")
    for p in breakdown["per_finding_penalties"]:
        print(f"    {p['category']}/{p['severity']}: penalty={p['final_penalty']}")

    # Test case 4: Low-confidence findings should hurt less
    test_findings_3 = [
        {"severity": "must_raise", "category": "other_risk", "confidence": 0.3, "semantic_check": {"verdict": "UNCERTAIN"}},
        {"severity": "must_raise", "category": "other_risk", "confidence": 0.95, "semantic_check": {"verdict": "YES"}},
    ]
    score, breakdown = scorer.calculate_score(test_findings_3)
    print(f"\n2 findings (one low conf, one high): score={score}")
    for p in breakdown["per_finding_penalties"]:
        print(f"    conf={p['confidence']}: penalty={p['final_penalty']}")
