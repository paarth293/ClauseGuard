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
            missing = [f for f in required_fields if f not in finding or not finding[f]]
            checks["schema_valid"] = "PASS" if not missing else f"FAIL (Missing: {missing})"
            
            # 2. Grounding Check (Does the quote actually exist in the raw text?)
            quote = finding.get("quote", "")
            if quote:
                normalized_quote = self._normalize(quote)
                # Pure Python string match (No AI involved)
                if normalized_quote in normalized_source:
                    checks["grounding"] = "PASS"
                else:
                    checks["grounding"] = "FAIL (Quote not found in source text)"
            else:
                checks["grounding"] = "FAIL (No quote provided by AI)"
                
            # 3. Confidence Check
            confidence = finding.get("confidence", 0.0)
            if float(confidence) >= 0.6:
                checks["confidence"] = "PASS"
            else:
                checks["confidence"] = f"FAIL (Low confidence: {confidence})"
                
            # Attach the test results to the finding for transparency
            finding["verification_checks"] = checks
            
            # THE KILL SWITCH: If grounding fails, we discard the finding entirely
            if checks["grounding"] == "PASS":
                verified_findings.append(finding)
                
        return verified_findings

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
    from ingestion import IngestionPipeline
    from analyzer import StructuredAnalyzer
    
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