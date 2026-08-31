"""
Blended Score Calculator

Combines two scoring approaches for maximum consistency:
  1. LLM-based weighted score (captures nuance, context-specific risks)
  2. Rule-based deterministic score (stable anchor, always same for same text)

Final score = α × rule_score + (1 - α) × llm_score

The rule-based score acts as a "stability anchor" — even if the LLM varies
slightly between runs, the final score stays within a tight band because
the rule-based component never changes.

α (alpha) controls the blend:
  - α = 0.7 → heavy rule-based weight (very stable, slightly less nuanced)
  - α = 0.5 → balanced (recommended)
  - α = 0.3 → heavy LLM weight (more nuanced, less stable)

For industry-grade consistency, we default to α = 0.6 (60% rule-based).
"""

from typing import Optional
from .scorer import RiskScorer
from .rule_scorer import RuleScorer


# ── Configuration ────────────────────────────────────────────────────────────

DEFAULT_ALPHA = 0.6  # 60% rule-based, 40% LLM-based


class BlendedScorer:
    """
    Combines rule-based and LLM-based scoring for consistent, nuanced results.
    """

    def __init__(self, alpha: float = DEFAULT_ALPHA):
        """
        Args:
            alpha: Weight for rule-based score (0.0 to 1.0).
                   0.6 means 60% rule-based + 40% LLM-based.
        """
        self.alpha = alpha
        self.llm_scorer = RiskScorer()
        self.rule_scorer = RuleScorer()

    def calculate_score(self, findings: list[dict], contract_text: str) -> tuple[int, dict]:
        """
        Calculate blended score from both LLM findings and rule-based analysis.

        Args:
            findings: Verified findings from the LLM pipeline
            contract_text: Raw contract text for rule-based analysis

        Returns:
            (score, full_breakdown) where score is 0-100
        """
        # ── Component 1: LLM-based score ─────────────────────────────────
        llm_score, llm_breakdown = self.llm_scorer.calculate_score(findings)

        # ── Component 2: Rule-based score (deterministic) ────────────────
        rule_score, rule_breakdown = self.rule_scorer.calculate_score(contract_text)

        # ── Blend ────────────────────────────────────────────────────────
        blended_score = round(
            self.alpha * rule_score + (1.0 - self.alpha) * llm_score
        )
        blended_score = max(0, min(100, blended_score))

        # ── Stability band: compute the range if LLM varied ──────────────
        # This tells the user how much the score could theoretically vary
        # if run without consensus/caching
        llm_variance_bound = round(abs(llm_score - rule_score) * (1.0 - self.alpha))

        breakdown = {
            "blended_score": blended_score,
            "llm_score": llm_score,
            "rule_score": rule_score,
            "alpha": self.alpha,
            "blending_formula": f"{self.alpha:.0%} × {rule_score} + {(1-self.alpha):.0%} × {llm_score} = {blended_score}",
            "stability_band": f"±{llm_variance_bound} points",
            "llm_breakdown": llm_breakdown,
            "rule_breakdown": rule_breakdown,
        }

        return blended_score, breakdown


# ── Standalone Test ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    scorer = BlendedScorer(alpha=0.6)

    # Mock findings
    findings = [
        {"severity": "must_raise", "category": "ip_ownership", "confidence": 0.95,
         "semantic_check": {"verdict": "YES"}},
        {"severity": "must_raise", "category": "payment_terms", "confidence": 0.88,
         "semantic_check": {"verdict": "YES"}},
    ]

    contract_text = """
    STATEMENT OF WORK
    Section 1. Services
    The Freelancer agrees to provide web development services.
    Section 2. Payment Terms
    Client shall pay Freelancer within 90 days of invoice receipt.
    Section 3. IP Ownership
    Freelancer agrees that all work product, including all prior inventions,
    pre-existing background IP, shall become the exclusive property of the Client.
    Section 4. Non-Compete
    Freelancer agrees not to engage in similar work for 24 months.
    """

    score, breakdown = scorer.calculate_score(findings, contract_text)

    print(f"Blended Score: {score}/100")
    print(f"  LLM score:   {breakdown['llm_score']}")
    print(f"  Rule score:  {breakdown['rule_score']}")
    print(f"  Formula:     {breakdown['blending_formula']}")
    print(f"  Stability:   {breakdown['stability_band']}")
    print()
    print("Rule breakdown:")
    for r in breakdown["rule_breakdown"]["applied_rules"]:
        print(f"  - {r['rule']}: -{r['deduction']} ({r['description']})")

    # Verify determinism of rule component
    scores = [scorer.calculate_score(findings, contract_text)[0] for _ in range(5)]
    print(f"\nBlended score determinism: {scores}")
    print(f"Variance: {max(scores) - min(scores)} points")
