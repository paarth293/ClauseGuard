import json
import os
import asyncio
from dotenv import load_dotenv
from groq import AsyncGroq

load_dotenv()

class SemanticVerifier:
    def __init__(self):
        self.client = AsyncGroq()
        # openai/gpt-oss-20b is fast and reliable for this binary YES/NO task
        self.model = "openai/gpt-oss-20b"

    async def verify_interpretation(self, verified_findings: list) -> list:
        """
        Takes findings that passed deterministic grounding and asks the LLM concurrently:
        'Does this quote actually support this claimed risk?'
        """
        if not verified_findings:
            return []
            
        tasks = [self._verify_single(finding) for finding in verified_findings]
        results = await asyncio.gather(*tasks)
        
        # Filter out findings that were dropped (returned None)
        return [res for res in results if res is not None]

    async def _verify_single(self, finding: dict) -> dict:
        quote = finding.get("quote", "")
        category = finding.get("category", "")
        explanation = finding.get("explanation", "")
        system_prompt = """
        You are a strict legal verification AI. Your ONLY job is to determine whether a quoted contract clause actually supports the claimed risk.
        
        Respond with STRICT JSON in this exact format:
        {
            "verdict": "YES" | "NO" | "UNCERTAIN",
            "reason": "Brief 1-sentence explanation of why"
        }
        
        RULES:
        - Answer YES only if the quote clearly supports the explanation.
        - Answer NO if the quote is irrelevant, contradicts the explanation, or is being misinterpreted.
        - Answer UNCERTAIN if the quote could easily mean something else.
        """
        
        user_prompt = f"""
        CONTRACT QUOTE: "{quote}"
        
        CLAIMED RISK:
        Category: {category}
        Explanation: {explanation}
        
        TASK: Does the quote above actually support this claimed risk?
        """
        
        try:
            response = await self.client.chat.completions.create(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                model=self.model,
                temperature=0.0, # Zero temperature so it doesn't change its mind
                response_format={"type": "json_object"}
            )
            
            verification_result = json.loads(response.choices[0].message.content)
            
            # Attach the semantic check results to the finding for our logs
            finding["semantic_check"] = verification_result
            
            verdict = verification_result.get("verdict", "UNCERTAIN").upper()
            # Only DROP a finding if the LLM explicitly says NO.
            # UNCERTAIN findings are kept — the human reviewer can make the final call.
            if verdict != "NO":
                return finding
            return None
                
        except Exception as e:
            print(f"[SEMANTIC VERIFIER ERROR] {e}")
            # On API error, keep the finding rather than silently discarding it
            finding["semantic_check"] = {"verdict": "PASS_ON_ERROR", "reason": str(e)}
            return finding

# --- Testing Code ---
if __name__ == "__main__":
    from .ingestion import IngestionPipeline
    from .analyzer import StructuredAnalyzer
    from .verifier import DeterministicVerifier
    
    async def run_test():
        print("Running pipeline up to Semantic Verification...")
        test_path = os.path.join(os.path.dirname(__file__), "../contracts/sow_002_seeded.txt")
        
        parsed_text = IngestionPipeline().process(test_path)["parsed_text"]
        findings = await StructuredAnalyzer().analyze(parsed_text)
        findings = findings.get("findings", [])
        det_verified = DeterministicVerifier().verify(findings, parsed_text)
        
        print(f"\nSending {len(det_verified)} finding(s) to Semantic Verifier...")
        sem_verifier = SemanticVerifier()
        
        # Run the semantic verification
        final_findings = await sem_verifier.verify_interpretation(det_verified)
        
        print("\n" + "="*50)
        print("SEMANTIC VERIFICATION RESULTS:")
        print("="*50)
        print(json.dumps(final_findings, indent=4))
        
    asyncio.run(run_test())