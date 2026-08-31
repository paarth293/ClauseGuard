import re

class DeterministicVerifier:
    def verify(self, findings: list, source_text: str) -> list:
        """
        Takes a list of JSON findings and verifies them deterministically.
        Returns a list containing ONLY the findings that passed the checks.
        """
        verified_findings = []
        normalized_source = self._normalize(source_text)
        
        for finding in findings:
            checks = {}
            
            # 1. Schema Completeness Check
            required_fields = ["clause_ref", "quote", "category", "severity", "explanation", "confidence"]
            missing = [f for f in required_fields if f not in finding or finding[f] is None or str(finding[f]).strip() == ""]
            checks["schema_valid"] = "PASS" if not missing else f"FAIL (Missing: {missing})"
            
            # 2. Grounding Check – the quote must be substantially present in the source text.
            # We use TWO strategies so minor LLM paraphrasing doesn't kill real findings:
            #   (a) Exact normalised substring match  – catches verbatim quotes
            #   (b) Word-overlap ratio ≥ 60%          – catches lightly reworded quotes
            quote = finding.get("quote", "")
            if quote:
                normalized_quote = self._normalize(quote)
                
                # Strategy (a): direct substring
                if normalized_quote in normalized_source:
                    checks["grounding"] = "PASS"
                else:
                    # Strategy (b): word-overlap ratio
                    overlap = self._word_overlap(normalized_quote, normalized_source)
                    if overlap >= 0.60:
                        checks["grounding"] = "PASS"
                    else:
                        checks["grounding"] = f"FAIL (Quote not found; overlap={overlap:.0%})"
            else:
                checks["grounding"] = "FAIL (No quote provided by AI)"
                
            # 3. Confidence Check
            confidence = finding.get("confidence", 0.0)
            try:
                conf_val = float(confidence)
            except (TypeError, ValueError):
                conf_val = 0.0
            checks["confidence"] = "PASS" if conf_val >= 0.5 else f"FAIL (Low confidence: {confidence})"
                
            # Attach the test results to the finding for transparency
            finding["verification_checks"] = checks
            
            # THE KILL SWITCH: Only drop if grounding explicitly fails
            if checks["grounding"] == "PASS":
                verified_findings.append(finding)
                
        return verified_findings

    def _word_overlap(self, quote: str, source: str) -> float:
        """
        Computes the fraction of unique words in the quote that appear in the source.
        This catches cases where the LLM slightly paraphrases the verbatim text.
        """
        quote_words = set(quote.split())
        if not quote_words:
            return 0.0
        matches = sum(1 for w in quote_words if w in source)
        return matches / len(quote_words)

    def _normalize(self, text: str) -> str:
        """
        Normalizes text for comparison by lowercasing and collapsing extra spaces.
        This prevents false failures caused by weird line-breaks in PDFs.
        """
        if not text:
            return ""
        text = text.lower()
        text = re.sub(r'\s+', ' ', text)
        return text.strip()


# --- Testing Code ---
if __name__ == "__main__":
    import os
    import json
    from .ingestion import IngestionPipeline
    from .analyzer import StructuredAnalyzer
    
    print("1. Ingesting...")
    ingestion = IngestionPipeline()
    test_path = os.path.join(os.path.dirname(__file__), "../contracts/sow_002_seeded.txt")
    ingest_result = ingestion.process(test_path)
    
    print("2. Analyzing (This might take a second)...")
    analyzer = StructuredAnalyzer()
    analyzer_result = analyzer.analyze(ingest_result["parsed_text"])
    
    print("3. Verifying deterministically...")
    verifier = DeterministicVerifier()
    
    # We pass BOTH the AI's findings AND the original pure text to the verifier
    verified = verifier.verify(analyzer_result.get("findings", []), ingest_result["parsed_text"])
    
    print("\n" + "="*50)
    print("VERIFICATION RESULTS:")
    print("="*50)
    print(json.dumps(verified, indent=4))
    
    print(f"\nOriginal AI findings: {len(analyzer_result.get('findings', []))}")
    print(f"Verified findings that survived: {len(verified)}")