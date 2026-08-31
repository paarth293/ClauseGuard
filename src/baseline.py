import os
from dotenv import load_dotenv
from groq import Groq
from .ingestion import IngestionPipeline

# Load environment variables from the .env file (this loads GROQ_API_KEY)
load_dotenv()

class BaselineAnalyzer:
    def __init__(self):
        # Initialize the Groq client. It automatically finds the API key in your environment.
        self.client = Groq()
        # We use Llama 3.1 70B on Groq - fast and capable
        self.model = "llama-3.1-70b-versatile"

    def analyze(self, contract_text: str) -> str:
        """
        Runs a basic, unstructured 'Find all risks' prompt.
        This represents how most people use AI for contracts, and serves as our baseline to beat.
        """
        prompt = f"""
        You are a legal assistant reviewing a freelancer contract.
        Please read the following contract and list any risks or issues the freelancer should be aware of.
        
        CONTRACT TEXT:
        {contract_text}
        """

        try:
            # Standard API chat completion call
            response = self.client.chat.completions.create(
                messages=[
                    {"role": "system", "content": "You are a helpful legal assistant."},
                    {"role": "user", "content": prompt}
                ],
                model=self.model,
                temperature=0.2, # Low temperature to keep the AI analytical and less creative
            )
            
            # Return the free-form text response from the AI
            return response.choices[0].message.content
            
        except Exception as e:
            return f"Error during analysis: {str(e)}"

# --- Testing Code ---
if __name__ == "__main__":
    import sys
    # Fix Unicode printing on Windows terminals (cp1252 can't handle all Unicode chars)
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    print("1. Ingesting the 'Seeded' contract...")
    ingestion = IngestionPipeline()
    
    # We will test the Baseline against our dangerous seeded contract
    test_path = os.path.join(os.path.dirname(__file__), "../contracts/sow_002_seeded.txt")
    ingest_result = ingestion.process(test_path)
    
    if ingest_result["status"] == "SUCCESS":
        print("2. Running Baseline Analysis (This might take a few seconds)...")
        analyzer = BaselineAnalyzer()
        
        # Pass the clean text from the ingestion pipeline to our AI
        analysis_result = analyzer.analyze(ingest_result["parsed_text"])
        
        print("\n" + "="*50)
        print("BASELINE ANALYSIS RESULT:")
        print("="*50)
        print(analysis_result)
    else:
        print(f"Ingestion failed: {ingest_result.get('error')}")