import json
import os
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

class SemanticVerifier:
    def __init__(self):
        self.client = Groq()
        # We use a smaller, much faster model for this simple binary task to save time/money
        self.model = "llama-3.1-8b-instant" 

    def verify_interpretation(self, verified_findings: list) -> list:
        """
        Takes findings that passed deterministic grounding and asks the LLM:
        'Does this quote actually support this claimed risk?'
        """
        semantically_verified = []
        
        for finding in verified_findings:
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
                response = self.client.chat.completions.create(
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
                
                # THE SECOND KILL SWITCH: If the LLM says "NO" or "UNCERTAIN", we drop the finding!
                if verification_result.get("verdict") == "YES":
                    semantically_verified.append(finding)
                    
            except Exception as e:
                print(f"Semantic Verification Error: {e}")
                
        return semantically_verified

# --- Testing Code ---
if __name__ == "__main__":
    from .ingestion import IngestionPipeline
    from .analyzer import StructuredAnalyzer
    from .verifier import DeterministicVerifier
    
    print("Running pipeline up to Semantic Verification...")
    test_path = os.path.join(os.path.dirname(__file__), "../contracts/sow_002_seeded.txt")
    
    parsed_text = IngestionPipeline().process(test_path)["parsed_text"]
    findings = StructuredAnalyzer().analyze(parsed_text).get("findings", [])
    det_verified = DeterministicVerifier().verify(findings, parsed_text)
    
    print(f"\nSending {len(det_verified)} finding(s) to Semantic Verifier...")
    sem_verifier = SemanticVerifier()
    
    # Run the semantic verification
    final_findings = sem_verifier.verify_interpretation(det_verified)
    
    print("\n" + "="*50)
    print("SEMANTIC VERIFICATION RESULTS:")
    print("="*50)
    print(json.dumps(final_findings, indent=4))