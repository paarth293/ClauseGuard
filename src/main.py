import sys
import time

# Fix Unicode printing on Windows terminals (cp1252 cannot handle all Unicode chars)
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from .ingestion import IngestionPipeline
from .analyzer import StructuredAnalyzer
from .verifier import DeterministicVerifier
from .semantic_verifier import SemanticVerifier
from .synthesizer import ReportSynthesizer

def run_clauseguard(file_path: str):
    print(f"Starting ClauseGuard review for: {file_path}")
    print("-" * 50)
    
    # Start the timer to calculate latency
    start_time = time.time()
    
    # 1. Ingestion
    print("[1/5] Ingesting document...")
    ingest_result = IngestionPipeline().process(file_path)
    if ingest_result["status"] != "SUCCESS":
        print(f"\n❌ FATAL ERROR: Ingestion failed.\nDetails: {ingest_result.get('error')}")
        return
    parsed_text = ingest_result["parsed_text"]
    
    # 2. Analysis
    print("[2/5] Running LLM analysis (Extracting structured risks)...")
    analyzer_result = StructuredAnalyzer().analyze(parsed_text)
    raw_findings = analyzer_result.get("findings", [])
    print(f"      Found {len(raw_findings)} potential risks.")
    
    # 3. Deterministic Verification
    print("[3/5] Verifying quotes (Anti-Hallucination check)...")
    det_verified = DeterministicVerifier().verify(raw_findings, parsed_text)
    print(f"      {len(det_verified)} risks passed grounding verification.")
    
    # 4. Semantic Verification
    print("[4/5] Verifying legal interpretation (Logic check)...")
    sem_verified = SemanticVerifier().verify_interpretation(det_verified)
    print(f"      {len(sem_verified)} risks passed semantic verification.")
    
    # 5. Synthesis
    print("[5/5] Synthesizing final report...")
    final_report = ReportSynthesizer().generate_report(sem_verified)
    
    end_time = time.time()
    
    print("\n" + "="*60)
    print(" FINAL CLAUSEGUARD REPORT")
    print("="*60 + "\n")
    
    # Print the beautiful markdown report
    print(final_report)
    
    print("\n" + "="*60)
    print(f"⏱️ Total Review Time: {end_time - start_time:.2f} seconds")
    print("="*60)

if __name__ == "__main__":
    # Ensure the user provided a file path when they ran the script
    if len(sys.argv) < 2:
        print("Usage: uv run python src/main.py <path_to_contract>")
        sys.exit(1)
        
    contract_path = sys.argv[1]
    run_clauseguard(contract_path)