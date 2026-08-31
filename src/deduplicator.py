"""
Findings Deduplicator

The LLM analyzer may return multiple findings that describe the same risk
(e.g., two findings about IP ownership in Section 3 with slightly different quotes).
This module deduplicates findings to ensure each unique risk appears exactly once.

Strategy:
  1. Exact dedup: same clause_ref + same category = duplicate
  2. Quote-overlap dedup: if two findings share >80% of their quote text, keep the
     one with higher confidence.
  3. When in doubt, keep the finding with higher confidence.
"""

from typing import Optional


# ── Configuration ────────────────────────────────────────────────────────────

QUOTE_OVERLAP_THRESHOLD = 0.80  # If 80%+ of quote words overlap, treat as duplicate


class FindingsDeduplicator:
    """
    Removes duplicate findings from the LLM output.
    Returns a deduplicated list, keeping the highest-confidence version of each unique finding.
    """

    def deduplicate(self, findings: list[dict]) -> list[dict]:
        if not findings:
            return []

        # Sort by confidence descending so we keep the best version
        sorted_findings = sorted(
            findings,
            key=lambda f: float(f.get("confidence", 0)),
            reverse=True
        )

        kept: list[dict] = []

        for candidate in sorted_findings:
            if self._is_duplicate(candidate, kept):
                continue
            kept.append(candidate)

        return kept

    def _is_duplicate(self, candidate: dict, kept: list[dict]) -> bool:
        """Check if the candidate is a duplicate of any already-kept finding.
        
        IMPORTANT: Two findings are only duplicates if they describe the SAME risk.
        Same risk means: same category AND (same clause_ref OR high quote overlap).
        
        Different categories = different risks, even if quotes overlap.
        This prevents dropping e.g. a 'kill_fee' finding that shares a quote
        with an 'other_risk' finding about the same termination clause.
        """
        candidate_clause = candidate.get("clause_ref", "").lower().strip()
        candidate_category = candidate.get("category", "").lower().strip()
        candidate_quote = candidate.get("quote", "").lower().strip()

        for existing in kept:
            existing_clause = existing.get("clause_ref", "").lower().strip()
            existing_category = existing.get("category", "").lower().strip()
            existing_quote = existing.get("quote", "").lower().strip()

            # DIFFERENT categories = DIFFERENT risks. Never dedup across categories.
            if candidate_category != existing_category:
                continue

            # Same category now — check if it's the same specific risk:
            # Strategy 1: Same clause reference AND same category = duplicate
            if candidate_clause == existing_clause:
                return True

            # Strategy 2: Same category + high quote text overlap = duplicate
            if candidate_quote and existing_quote:
                overlap = self._quote_overlap(candidate_quote, existing_quote)
                if overlap >= QUOTE_OVERLAP_THRESHOLD:
                    return True

        return False

    def _quote_overlap(self, quote_a: str, quote_b: str) -> float:
        """Compute word-level Jaccard-like overlap between two quotes."""
        words_a = set(quote_a.split())
        words_b = set(quote_b.split())
        if not words_a or not words_b:
            return 0.0
        intersection = words_a & words_b
        union = words_a | words_b
        return len(intersection) / len(union)


# ── Standalone Test ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    dedup = FindingsDeduplicator()

    test_findings = [
        {"clause_ref": "Section 3", "category": "ip_ownership", "confidence": 0.9,
         "quote": "Freelancer agrees that all work product shall become the exclusive property of the Client."},
        {"clause_ref": "Section 3", "category": "ip_ownership", "confidence": 0.7,
         "quote": "all work product, including all prior inventions, shall become the exclusive property of the Client."},
        {"clause_ref": "Section 2", "category": "payment_terms", "confidence": 0.85,
         "quote": "Client shall pay Freelancer within 15 days of invoice receipt."},
        {"clause_ref": "Section 3", "category": "ip_ownership", "confidence": 0.6,
         "quote": "Freelancer agrees that all work product shall become property of the Client."},
    ]

    result = dedup.deduplicate(test_findings)
    print(f"Input: {len(test_findings)} findings")
    print(f"Output: {len(result)} findings after deduplication")
    for f in result:
        print(f"  - [{f['category']}] {f['clause_ref']} (conf={f['confidence']})")
