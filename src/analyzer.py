import os
import json
from dotenv import load_dotenv
from groq import Groq
from .ingestion import IngestionPipeline

load_dotenv()

class StructuredAnalyzer:
    def __init__(self):
        self.client = Groq()
        self.model = "llama-3.1-70b-versatile"

    def analyze(self, contract_text: str) -> dict:
        """
        Analyzes the contract and forces the LLM to return strict JSON data.
        This provides structured findings that our code can programmatically verify.
        """
        
        # The System Prompt is where we define the strict JSON schema
        system_prompt = """
        You are ClauseGuard, an expert legal AI reviewing freelancer contracts.
        Your ONLY job is to analyze the contract according to the provided taxonomy and output STRICT JSON.
        
        You MUST return your response as a JSON object containing a single key named "findings", which is a list of risk objects.
        
        Each finding in the list MUST adhere to this exact schema:
        {
            "clause_ref": "Exact section or clause reference (e.g. 'Section 3.2')",
            "quote": "Direct, verbatim quote from the contract text",
            "category": "Must be one of: [payment_terms, kill_fee, liability_cap, ip_ownership, indemnification, other_risk]",
            "severity": "Must be one of: [must_raise, worth_raising]",
            "explanation": "Plain-English explanation of what this means for the freelancer",
            "confidence": A number between 0.0 and 1.0 representing your confidence
        }
        
        CRITICAL RULES:
        1. If no risks are found, return {"findings": []}
        2. Never output conversational text. Output ONLY valid JSON.
        3. Every finding MUST include a direct quote from the text.
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
            print(f"Analyzer Error: {e}")
            return {"findings": []}

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