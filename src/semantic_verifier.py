import json
import os
import asyncio
from dotenv import load_dotenv
from .llm import get_openai_client, get_model

load_dotenv()

MAX_RETRIES = 3
RETRY_DELAY = 3.0  # seconds (increased for rate limit handling)

class SemanticVerifier:
    def __init__(self):
        self.client = get_openai_client()
        self.model = get_model("verification")

    async def verify_interpretation(self, verified_findings: list[dict], contract_text: str = "") -> list[dict]:
        """
        Takes findings that passed deterministic grounding and asks the LLM concurrently:
        'Does this quote actually support this claimed risk in the context of the contract?'

        Args:
            verified_findings: Findings that passed deterministic verification
            contract_text: The full contract text for context (critical for accurate verification)

        Verdict handling:
          - YES: finding is kept (semantic verification passed)
          - UNCERTAIN: finding is kept but tagged (soft pass)
          - NO: finding is DROPPED (semantic verification failed)
          - On API error after retries: finding is KEPT with UNCERTAIN tag
            (fail-open for semantic layer — deterministic verifier already caught
             bad quotes, so semantic is a quality filter not a safety gate)
        """
        if not verified_findings:
            return []
            
        # Process findings in batches to respect rate limits.
        # Running all concurrently can exceed TPM limits on Groq.
        BATCH_SIZE = 3
        BATCH_DELAY = 2.0  # seconds between batches
        all_results = []
        
        for i in range(0, len(verified_findings), BATCH_SIZE):
            batch = verified_findings[i:i + BATCH_SIZE]
            tasks = [self._verify_single(finding, contract_text) for finding in batch]
            batch_results = await asyncio.gather(*tasks)
            all_results.extend(batch_results)
            
            # Add delay between batches to avoid rate limiting
            if i + BATCH_SIZE < len(verified_findings):
                await asyncio.sleep(BATCH_DELAY)
        
        # Filter out findings that were dropped (returned None)
        return [res for res in all_results if res is not None]

    async def _verify_single(self, finding: dict, contract_text: str = "") -> dict:
        quote = finding.get("quote", "")
        category = finding.get("category", "")
        explanation = finding.get("explanation", "")
        severity = finding.get("severity", "")
        clause_ref = finding.get("clause_ref", "")
        
        system_prompt = """
        You are a strict legal verification AI specializing in freelancer contract risk analysis.
        Your ONLY job is to determine whether a quoted contract clause actually represents the claimed risk.
        
        You will receive:
        1. The full contract text (for context)
        2. A specific quote from the contract
        3. A claimed risk (category, severity, explanation)
        
        Respond with STRICT JSON in this exact format:
        {
            "verdict": "YES" | "NO" | "UNCERTAIN",
            "reason": "Brief 1-sentence explanation of why"
        }
        
        VERDICT RULES:
        - YES: The quote, in the context of the full contract, supports the claimed risk.
          The risk is real and would disadvantage a freelancer.
        - NO: The quote does NOT support the claimed risk. Either:
          (a) The quote is taken out of context and the full contract is actually fair
          (b) The risk category is mislabeled
          (c) The explanation misrepresents what the clause actually does
        - UNCERTAIN: You cannot determine from the quote and context whether the risk is valid.
        
        CRITICAL: Consider the FULL contract context, not just the quote in isolation.
        A clause might look risky in isolation but be balanced by other provisions.
        Conversely, a seemingly benign clause might be risky given the broader context.
        """
        
        # Build the user prompt with contract context
        context_section = ""
        if contract_text:
            # Truncate contract to avoid token limits, but keep enough context
            truncated = contract_text[:8000] if len(contract_text) > 8000 else contract_text
            context_section = f"FULL CONTRACT TEXT:\n{truncated}\n\n"
        
        user_prompt = f"""{context_section}SPECIFIC QUOTE FROM CONTRACT: "{quote}"

CLAIMED RISK:
Clause Reference: {clause_ref}
Category: {category}
Severity: {severity}
Explanation: {explanation}

TASK: Does the quote above, in the context of the full contract, actually represent this claimed risk?
Respond with STRICT JSON: {{"verdict": "YES" or "NO" or "UNCERTAIN", "reason": "..."}}
"""
        
        last_error = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                response = await self.client.chat.completions.create(
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    model=self.model,
                    temperature=0.0,
                    response_format={"type": "json_object"}
                )
                
                verification_result = json.loads(response.choices[0].message.content)
                
                # Attach the semantic check results to the finding for our logs
                finding["semantic_check"] = verification_result
                
                verdict = verification_result.get("verdict", "UNCERTAIN").upper()
                # YES or UNCERTAIN = keep the finding
                if verdict in ("YES", "UNCERTAIN"):
                    return finding
                # NO verdict = drop the finding
                return None

            except Exception as e:
                last_error = e
                if attempt < MAX_RETRIES:
                    await asyncio.sleep(RETRY_DELAY * attempt)
        
        # All retries exhausted — fail-open: keep the finding tagged as UNCERTAIN
        # The deterministic verifier already validated the quote exists in the text,
        # so this is likely a real finding that just had a transient API error.
        print(f"[SEMANTIC VERIFIER] Retries exhausted for finding '{category}' ({last_error}). Keeping as UNCERTAIN.")
        finding["semantic_check"] = {"verdict": "UNCERTAIN", "reason": f"API error after {MAX_RETRIES} retries: {last_error}"}
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