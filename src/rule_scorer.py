"""
Deterministic Rule-Based Scorer

The LLM-based scorer produces different scores each run because the LLM
finds slightly different things. This module provides a STABLE, deterministic
score based on rule-based text analysis that never changes for the same input.

Industry pattern: use rule-based scoring as a "baseline" and blend it with
the LLM score for consistency. The rule-based score is the "anchor" that
prevents the final score from jumping around.

Rules check for:
  - Payment terms quality (net-15 vs net-90 vs no terms)
  - Kill fee presence
  - IP ownership scope (reasonable vs blanket assignment)
  - Liability caps
  - Indemnification scope
  - Missing standard freelancer protections

Each rule returns a point deduction from 100. The result is fully deterministic.
"""

import re
from typing import Optional


# ── Rule Definitions ─────────────────────────────────────────────────────────
# Each rule is (name, pattern, deduction, description)
# pattern is a compiled regex or None (always applies)

RULES = [
    # ── Payment Terms ────────────────────────────────────────────────────
    {
        "name": "no_payment_terms",
        "pattern": None,  # Applied when no payment language is found at all
        "deduction": 12,
        "description": "No payment terms found in contract",
        "check": "absent",
        "keywords": ["payment", "invoice", "pay", "compensation", "fee", "rate"],
    },
    {
        "name": "slow_payment",
        "pattern": re.compile(r"(net\s*(\d{2,3}))", re.IGNORECASE),
        "deduction": 8,
        "description": "Payment terms exceed Net-30 (unfavorable to freelancer)",
        "check": "slow_payment",
    },
    {
        "name": "no_payment_schedule",
        "pattern": re.compile(
            r"(milestone|schedule|phased|installment|progress.*payment|payment.*milestone)",
            re.IGNORECASE,
        ),
        "deduction": 5,
        "description": "No milestone-based payment schedule (lump sum only)",
        "check": "absent_positive",
    },

    # ── Kill Fee / Termination ───────────────────────────────────────────
    {
        "name": "no_termination_clause",
        "pattern": re.compile(
            r"(terminat|cancel|end.*agreement|cease.*work|killed|kill.*fee)",
            re.IGNORECASE,
        ),
        "deduction": 10,
        "description": "No termination or kill fee clause found",
        "check": "absent_positive",
    },
    {
        "name": "no_kill_fee",
        "pattern": re.compile(
            r"(kill\s*fee|terminat.*fee|cancell.*fee|compensat.*terminat)",
            re.IGNORECASE,
        ),
        "deduction": 8,
        "description": "No explicit kill fee for project cancellation",
        "check": "absent_positive",
    },

    # ── IP Ownership ─────────────────────────────────────────────────────
    {
        "name": "blanket_ip_assignment",
        "pattern": re.compile(
            r"(all\s*(work|invention|intellectual|prior|background|pre.?existing))",
            re.IGNORECASE,
        ),
        "deduction": 12,
        "description": "Blanket IP assignment language (may claim pre-existing work)",
        "check": "present",
    },
    {
        "name": "ip_ownership_transfers",
        "pattern": re.compile(
            r"(become.*exclusive\s*property|transfer.*client|assign.*client|vest.*client)",
            re.IGNORECASE,
        ),
        "deduction": 7,
        "description": "IP transfers to client (standard but verify scope)",
        "check": "present",
    },
    {
        "name": "freelancer_retains_ip",
        "pattern": re.compile(
            r"(retains?\s*(all|their)?\s*rights|freelancer.*own|background\s*ip.*freelancer)",
            re.IGNORECASE,
        ),
        "deduction": -5,  # Negative = bonus (good for freelancer)
        "description": "Freelancer retains rights to pre-existing IP (positive)",
        "check": "present",
    },

    # ── Liability ────────────────────────────────────────────────────────
    {
        "name": "no_liability_cap",
        "pattern": re.compile(
            r"(liability.*cap|aggregate.*liability|maximum.*liability|limit.*liability)",
            re.IGNORECASE,
        ),
        "deduction": 10,
        "description": "No liability cap found (unlimited exposure)",
        "check": "absent_positive",
    },
    {
        "name": "unlimited_indemnification",
        "pattern": re.compile(
            r"(indemnif.*(?:all|any|every|all\s*claims|hold\s*harmless))",
            re.IGNORECASE,
        ),
        "deduction": 10,
        "description": "Broad/unlimited indemnification clause",
        "check": "present",
    },

    # ── Other Red Flags ──────────────────────────────────────────────────
    {
        "name": "non_compete",
        "pattern": re.compile(
            r"(non.?compete|restrict.*compet|not.*engage.*similar|exclusiv.*engagement)",
            re.IGNORECASE,
        ),
        "deduction": 8,
        "description": "Non-compete or exclusivity clause found",
        "check": "present",
    },
    {
        "name": "unilateral_modification",
        "pattern": re.compile(
            r"(modif.*at\s*(?:its|their)?\s*sole|amend.*sole\s*discretion|change.*without.*notice)",
            re.IGNORECASE,
        ),
        "deduction": 10,
        "description": "Client can unilaterally modify the agreement",
        "check": "present",
    },
    {
        "name": "governing_law_missing",
        "pattern": re.compile(
            r"(govern.*law|jurisdiction|applicable\s*law|dispute.*resolution|arbitrat)",
            re.IGNORECASE,
        ),
        "deduction": 5,
        "description": "No governing law or dispute resolution clause",
        "check": "absent_positive",
    },
]


class RuleScorer:
    """
    Deterministic, rule-based safety scorer.
    Produces the same score every time for the same input text.
    """

    def calculate_score(self, text: str) -> tuple[int, dict]:
        """
        Calculate a deterministic safety score from contract text.
        Returns (score, breakdown) where breakdown lists every rule applied.
        """
        if not text or len(text.strip()) < 50:
            return 50, {"applied_rules": [], "note": "Text too short for reliable analysis"}

        total_deduction = 0
        applied_rules = []

        for rule in RULES:
            rule_name = rule["name"]
            deduction = rule["deduction"]
            description = rule["description"]
            check_type = rule["check"]

            if check_type == "absent":
                # Check if key payment language is completely absent
                keywords = rule.get("keywords", [])
                found = any(re.search(rf"\b{kw}\b", text, re.IGNORECASE) for kw in keywords)
                if not found:
                    total_deduction += deduction
                    applied_rules.append({
                        "rule": rule_name,
                        "deduction": deduction,
                        "description": description,
                        "triggered": True,
                    })

            elif check_type == "absent_positive":
                # Rule triggers when the pattern is NOT found (missing protection)
                pattern = rule["pattern"]
                if pattern and not pattern.search(text):
                    total_deduction += deduction
                    applied_rules.append({
                        "rule": rule_name,
                        "deduction": deduction,
                        "description": description,
                        "triggered": True,
                    })

            elif check_type == "present":
                # Rule triggers when the risky pattern IS found
                pattern = rule["pattern"]
                if pattern and pattern.search(text):
                    total_deduction += deduction
                    applied_rules.append({
                        "rule": rule_name,
                        "deduction": deduction,
                        "description": description,
                        "triggered": True,
                    })

        score = max(0, min(100, 100 - total_deduction))

        return score, {
            "applied_rules": applied_rules,
            "total_deduction": total_deduction,
            "num_rules_triggered": len(applied_rules),
        }


# ── Standalone Test ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    scorer = RuleScorer()

    # Test with clean contract
    clean_text = """
    STATEMENT OF WORK
    Section 1. Services
    The Freelancer agrees to provide web development services as outlined in Appendix A.
    Section 2. Payment Terms
    Client shall pay Freelancer within 15 days of invoice receipt.
    Section 3. IP Ownership
    Freelancer retains all rights to pre-existing background IP.
    Custom code written specifically for this project transfers to the Client upon full payment.
    Section 4. Termination
    Either party may terminate with 30 days written notice. Client pays kill fee of 25% of remaining contract value.
    Section 5. Liability
    Aggregate liability shall not exceed total fees paid under this agreement.
    Section 6. Governing Law
    This agreement shall be governed by the laws of the State of New York.
    """

    # Test with bad contract
    bad_text = """
    STATEMENT OF WORK
    Section 1. Services
    The Freelancer agrees to provide web development services.
    Section 2. Payment Terms
    Client shall pay Freelancer within 90 days of invoice receipt.
    Section 3. IP Ownership
    Freelancer agrees that all work product, including all prior inventions, pre-existing background IP,
    and open-source tools used in this project, shall become the exclusive property of the Client.
    Section 4. Non-Compete
    Freelancer agrees not to engage in similar work for any competing business for 24 months.
    Section 5. Indemnification
    Freelancer shall indemnify Client for all claims arising from this agreement.
    """

    score_clean, breakdown_clean = scorer.calculate_score(clean_text)
    score_bad, breakdown_bad = scorer.calculate_score(bad_text)

    print("Clean contract:")
    print(f"  Score: {score_clean}/100 (deduction: {breakdown_clean['total_deduction']})")
    for r in breakdown_clean["applied_rules"]:
        print(f"    - {r['rule']}: -{r['deduction']} ({r['description']})")

    print(f"\nBad contract:")
    print(f"  Score: {score_bad}/100 (deduction: {breakdown_bad['total_deduction']})")
    for r in breakdown_bad["applied_rules"]:
        print(f"    - {r['rule']}: -{r['deduction']} ({r['description']})")

    # Verify determinism: run 5 times, should always be the same
    scores = [scorer.calculate_score(bad_text)[0] for _ in range(5)]
    print(f"\nDeterminism test: {scores}")
    assert len(set(scores)) == 1, "FAIL: scores are not deterministic!"
    print("✓ Deterministic: same score on every run")
