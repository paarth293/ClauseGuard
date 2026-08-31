import sys
import time
import asyncio

# Fix Unicode printing on Windows terminals (cp1252 cannot handle all Unicode chars)
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from .ingestion import IngestionPipeline
from .analyzer import StructuredAnalyzer
from .verifier import DeterministicVerifier
from .semantic_verifier import SemanticVerifier
from .synthesizer import ReportSynthesizer

async def run_clauseguard(file_path: str):
    """Runs the complete end-to-end pipeline."""
    start_time = time.time()
    
    print(f"Starting ClauseGuard review for: {file_path}")
    print("-" * 50)
    
    # 1. Ingestion
    print("[1/5] Ingesting document...")
    ingestion_result = IngestionPipeline().process(file_path)
    if ingestion_result["status"] != "SUCCESS":
        print(f"ERROR: {ingestion_result.get('error')}")
        return
        
    parsed_text = ingestion_result["parsed_text"]
    
    # 2. LLM Analysis
    print("[2/5] Running LLM analysis (Extracting structured risks)...")
    analyzer_result = await StructuredAnalyzer().analyze(parsed_text)
    raw_findings = analyzer_result.get("findings", [])
    print(f"      Found {len(raw_findings)} potential risks.")
    
    # 3. Deterministic Verification
    print("[3/5] Verifying quotes (Anti-Hallucination check)...")
    det_verified = DeterministicVerifier().verify(raw_findings, parsed_text)
    print(f"      {len(det_verified)} risks passed grounding verification.")
    
    # 4. Semantic Verification
    print("[4/5] Verifying legal interpretation (Logic check)...")
    sem_verified = await SemanticVerifier().verify_interpretation(det_verified)
    print(f"      {len(sem_verified)} risks passed semantic verification.")
    
    # 5. Synthesis
    print("[5/5] Synthesizing final report...\n")
    final_report = await ReportSynthesizer().generate_report(sem_verified)
    
    print("=" * 60)
    print(" FINAL CLAUSEGUARD REPORT")
    print("=" * 60)
    print(final_report)
    
    end_time = time.time()
    print("\n" + "=" * 60)
    print(f"⏱️ Total Review Time: {end_time - start_time:.2f} seconds")
    print("=" * 60)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m src.main <path_to_contract_file>")
        sys.exit(1)
        
    contract_path = sys.argv[1]
    asyncio.run(run_clauseguard(contract_path))