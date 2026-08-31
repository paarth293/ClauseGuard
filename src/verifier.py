import re
from typing import Optional


# ── Configuration ────────────────────────────────────────────────────────────

REQUIRED_FIELDS = ["clause_ref", "quote", "category", "severity", "explanation", "confidence"]
VALID_SEVERITIES = {"must_raise", "worth_raising"}
VALID_CATEGORIES = {
    "payment_terms", "kill_fee", "liability_cap",
    "ip_ownership", "indemnification", "other_risk"
}
MIN_CONFIDENCE = 0.5
MIN_GROUNDING_OVERLAP = 0.60  # 60% word overlap if exact match fails


class DeterministicVerifier:
    """
    Filters LLM findings through deterministic checks.
    Only findings that pass ALL checks are returned.
    """

    def verify(self, findings: list[dict], source_text: str) -> list[dict]:
        verified_findings = []
        normalized_source = self._normalize(source_text)
        
        for finding in findings:
            checks = {}

            # ── Check 1: Schema Completeness ──────────────────────────────
            missing = [
                f for f in REQUIRED_FIELDS
                if f not in finding or finding[f] is None or str(finding[f]).strip() == ""
            ]
            checks["schema_valid"] = "PASS" if not missing else f"FAIL (missing: {missing})"

            # ── Check 2: Category / Severity Validity ─────────────────────
            category = finding.get("category", "")
            severity = finding.get("severity", "")
            cat_ok = category in VALID_CATEGORIES
            sev_ok = severity in VALID_SEVERITIES
            checks["values_valid"] = (
                "PASS" if (cat_ok and sev_ok)
                else f"FAIL (category={category} valid={cat_ok}, severity={severity} valid={sev_ok})"
            )

            # ── Check 3: Grounding ────────────────────────────────────────
            quote = finding.get("quote", "")
            if quote:
                normalized_quote = self._normalize(quote)
                # Strategy A: direct substring match
                if normalized_quote in normalized_source:
                    checks["grounding"] = "PASS"
                else:
                    # Strategy B: word-overlap ratio
                    overlap = self._word_overlap(normalized_quote, normalized_source)
                    if overlap >= MIN_GROUNDING_OVERLAP:
                        checks["grounding"] = f"PASS (overlap={overlap:.0%})"
                    else:
                        checks["grounding"] = f"FAIL (quote not found; overlap={overlap:.0%})"
            else:
                checks["grounding"] = "FAIL (no quote provided)"

            # ── Check 4: Confidence Threshold ─────────────────────────────
            confidence = finding.get("confidence", 0.0)
            try:
                conf_val = float(confidence)
            except (TypeError, ValueError):
                conf_val = 0.0
            checks["confidence"] = (
                "PASS" if conf_val >= MIN_CONFIDENCE
                else f"FAIL (confidence={conf_val:.2f} < {MIN_CONFIDENCE})"
            )

            # ── Attach verification results for audit trail ───────────────
            finding["verification_checks"] = checks

            # ── KILL SWITCH: ALL checks must pass ─────────────────────────
            all_passed = all(v == "PASS" or v.startswith("PASS ") for v in checks.values())
            if all_passed:
                verified_findings.append(finding)
                
        return verified_findings

    # ── Helpers ───────────────────────────────────────────────────────────

    def _word_overlap(self, quote: str, source: str) -> float:
        """Fraction of unique words in the quote that appear in the source."""
        quote_words = set(quote.split())
        if not quote_words:
            return 0.0
        matches = sum(1 for w in quote_words if w in source)
        return matches / len(quote_words)

    def _normalize(self, text: str) -> str:
        """Lowercase and collapse whitespace for stable comparison."""
        if not text:
            return ""
        text = text.lower()
        text = re.sub(r'\s+', ' ', text)
        return text.strip()


# ── Standalone Test ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    import os
    import json
    import asyncio
    from .ingestion import IngestionPipeline
    from .analyzer import StructuredAnalyzer

    print("1. Ingesting...")
    ingestion = IngestionPipeline()
    test_path = os.path.join(os.path.dirname(__file__), "../contracts/sow_002_seeded.txt")
    ingest_result = ingestion.process(test_path)

    print("2. Analyzing...")
    analyzer = StructuredAnalyzer()
    analyzer_result = asyncio.run(analyzer.analyze(ingest_result["parsed_text"]))

    print("3. Verifying deterministically...")
    verifier = DeterministicVerifier()
    verified = verifier.verify(analyzer_result.get("findings", []), ingest_result["parsed_text"])

    print("\n" + "=" * 50)
    print("VERIFICATION RESULTS:")
    print("=" * 50)
    print(json.dumps(verified, indent=4))
    print(f"\nOriginal AI findings: {len(analyzer_result.get('findings', []))}")
    print(f"Verified findings that survived: {len(verified)}")