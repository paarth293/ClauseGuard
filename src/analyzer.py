import os
import json
from dotenv import load_dotenv
from groq import Groq
from .ingestion import IngestionPipeline

load_dotenv()

class StructuredAnalyzer:
    def __init__(self):
        self.client = Groq()
        # llama3-70b-8192 is the most reliable Groq model for strict JSON output
        self.model = "openai/gpt-oss-120b"

    def analyze(self, contract_text: str) -> dict:
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

Categories to look for (flag ALL that apply):
- payment_terms: Late payment, no payment schedule, vague milestones, client can withhold payment
- kill_fee: No kill fee, or project can be cancelled without compensation
- liability_cap: No cap on freelancer liability, or unlimited indemnification
- ip_ownership: Client claims ownership of ALL work including pre-existing IP, tools, or background IP
- indemnification: Freelancer must indemnify client for things outside their control
- other_risk: Non-compete, non-solicitation, jurisdiction issues, unilateral contract modification

Each finding MUST follow this EXACT JSON schema:
{
    "clause_ref": "The section number or heading (e.g. 'Section 3', 'Clause 5.2')",
    "quote": "Copy the EXACT verbatim text from the contract — do not paraphrase",
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
"""

        user_prompt = f"=== DOCUMENT DATA BEGIN ===\n{contract_text}\n=== DOCUMENT DATA END ==="

        try:
            response = self.client.chat.completions.create(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                model=self.model,
                temperature=0.1, # Extremely low temperature to ensure strict formatting
                response_format={"type": "json_object"} # Forces the API to output valid JSON
            )
            
            # Convert the string response into an actual Python dictionary
            raw_content = response.choices[0].message.content
            return json.loads(raw_content)
            
        except Exception as e:
            print(f"[ANALYZER ERROR] {type(e).__name__}: {e}")
            # Re-raise so the API surfaces the real error instead of silently returning no findings
            raise RuntimeError(f"Analyzer failed: {e}") from e

# --- Testing Code ---
if __name__ == "__main__":
    print("1. Ingesting the 'Seeded' contract...")
    ingestion = IngestionPipeline()
    test_path = os.path.join(os.path.dirname(__file__), "../contracts/sow_002_seeded.txt")
    ingest_result = ingestion.process(test_path)
    
    if ingest_result["status"] == "SUCCESS":
        print("2. Running Structured Analysis (Strict JSON)...")
        analyzer = StructuredAnalyzer()
        
        result_data = analyzer.analyze(ingest_result["parsed_text"])
        
        print("\n" + "="*50)
        print("STRUCTURED FINDINGS:")
        print("="*50)
        # json.dumps makes the dictionary print beautifully in the terminal
        print(json.dumps(result_data, indent=4))
        
        print(f"\nTotal Risks Found: {len(result_data.get('findings', []))}")