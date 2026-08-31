import os
import json
import asyncio
from dotenv import load_dotenv
from .llm import get_openai_client, get_model
from .ingestion import IngestionPipeline

load_dotenv()

# ── Configuration ────────────────────────────────────────────────────────────

MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 2.0


class StructuredAnalyzer:
    def __init__(self):
        self.client = get_openai_client()
        self.model = get_model("analysis")  # gpt-4o

    async def analyze(self, contract_text: str) -> dict:
        """
        Analyzes the contract and forces the LLM to return strict JSON data.
        This provides structured findings that our code can programmatically verify.
        """
        
        # The System Prompt is where we define the strict JSON schema
        system_prompt = """
You are ClauseGuard, an expert legal AI specializing in protecting freelancers from risky contract clauses.
Your ONLY job is to analyze the contract text for risks and output STRICT, VALID JSON.

You MUST return a JSON object with a single key "findings" containing a list of risk objects.
Be THOROUGH and PROACTIVE — flag any clause that could disadvantage the freelancer, even if subtle.

IMPORTANT: You must find risks in TWO ways:
1. EXISTING bad clauses — find clauses that are unfair, one-sided, or dangerous to the freelancer
2. MISSING standard protections — find when the contract OMITS protections that a fair contract should include

Categories to look for (flag ALL that apply):
- payment_terms: Late payment (Net-30+), no payment schedule, no milestone payments, vague payment terms, client can withhold/delay payment, no late payment penalty
- kill_fee: No kill fee clause, or project can be cancelled without compensation to the freelancer
- liability_cap: No cap on freelancer liability, unlimited liability exposure, missing aggregate liability limit
- ip_ownership: Client claims ownership of ALL work including pre-existing IP, background IP, tools, or open-source; blanket IP assignment; freelancer loses rights to their own prior work
- indemnification: Freelancer must indemnify client for things outside their control; one-sided indemnification; no mutual indemnification
- other_risk: Non-compete, non-solicitation, jurisdiction issues, unilateral contract modification, no governing law, no dispute resolution, no force majeure, no confidentiality boundaries, excessive exclusivity

Each finding MUST follow this EXACT JSON schema:
{
    "clause_ref": "The section number or heading (e.g. 'Section 3', 'Clause 5.2'). For MISSING clauses, use 'Missing: [clause name]' (e.g. 'Missing: Termination clause')",
    "quote": "Copy the EXACT verbatim text from the contract that demonstrates the risk. For MISSING clauses, quote the most relevant surrounding text that shows the gap.",
    "category": "one of: payment_terms, kill_fee, liability_cap, ip_ownership, indemnification, other_risk",
    "severity": "one of: must_raise, worth_raising",
    "explanation": "Plain-English explanation of why this is risky for the freelancer",
    "confidence": 0.85
}

CRITICAL RULES:
1. Output ONLY the JSON object — no preamble, no explanation text, no markdown code fences.
2. The "quote" field MUST be copied verbatim from the contract text.
3. If you genuinely find no risks, return {"findings": []}.
4. A confidence of 0.0 means you have no confidence; 1.0 means absolute certainty.
5. MISSING clauses are just as dangerous as bad clauses — always flag them.
6. Flag EVERYTHING — it is better to over-flag than to miss a risk.
"""

        user_prompt = f"=== DOCUMENT DATA BEGIN ===\n{contract_text}\n=== DOCUMENT DATA END ==="

        last_error = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                response = await self.client.chat.completions.create(
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    model=self.model,
                    temperature=0.0
                )

                raw_content = response.choices[0].message.content
                print(f"[DEBUG] Raw LLM Output: {raw_content}")

                # Clean markdown backticks if model didn't use response_format correctly
                cleaned_content = raw_content.strip()
                if cleaned_content.startswith("```json"):
                    cleaned_content = cleaned_content[7:]
                if cleaned_content.startswith("```"):
                    cleaned_content = cleaned_content[3:]
                if cleaned_content.endswith("```"):
                    cleaned_content = cleaned_content[:-3]
                cleaned_content = cleaned_content.strip()

                try:
                    result = json.loads(cleaned_content)
                except json.JSONDecodeError as e:
                    print(f"[DEBUG] JSON Decode Error: {e}")
                    raise

                # Validate that the response has the expected structure
                if "findings" not in result:
                    print(f"[DEBUG] 'findings' key missing. Result was: {result}")
                    result = {"findings": []}

                return result

            except Exception as e:
                last_error = e
                print(f"[ANALYZER] Attempt {attempt}/{MAX_RETRIES} failed: {type(e).__name__}: {e}")
                if attempt < MAX_RETRIES:
                    delay = RETRY_DELAY_SECONDS * attempt  # Linear backoff
                    print(f"[ANALYZER] Retrying in {delay:.1f}s...")
                    await asyncio.sleep(delay)

        # All retries exhausted
        raise RuntimeError(f"Analyzer failed after {MAX_RETRIES} attempts: {last_error}")

# --- Testing Code ---
if __name__ == "__main__":
    import asyncio
    from .ingestion import IngestionPipeline

    async def run_test():
        print("1. Ingesting the 'Seeded' contract...")
        ingestion = IngestionPipeline()
        test_path = os.path.join(os.path.dirname(__file__), "../contracts/sow_002_seeded.txt")
        ingest_result = ingestion.process(test_path)
        
        if ingest_result["status"] == "SUCCESS":
            print("2. Running Structured Analysis (Strict JSON)...")
            analyzer = StructuredAnalyzer()
            
            result_data = await analyzer.analyze(ingest_result["parsed_text"])
            
            print("\n" + "="*50)
            print("STRUCTURED FINDINGS:")
            print("="*50)
            # json.dumps makes the dictionary print beautifully in the terminal
            print(json.dumps(result_data, indent=4))
            
            print(f"\nTotal Risks Found: {len(result_data.get('findings', []))}")
            
    asyncio.run(run_test())