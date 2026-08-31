import sys
import os
import time
import asyncio

# Fix Unicode printing on Windows terminals (cp1252 cannot handle all Unicode chars)
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from .ingestion import IngestionPipeline
from .analyzer import StructuredAnalyzer
from .verifier import DeterministicVerifier
from .semantic_verifier import SemanticVerifier
from .deduplicator import FindingsDeduplicator
from .synthesizer import ReportSynthesizer
from .blended_scorer import BlendedScorer
from .consensus import ConsensusAnalyzer
from .cache import DocumentCache
from .logger import PipelineLogger

async def run_clauseguard(file_path: str, use_consensus: bool = True, use_cache: bool = True):
    """
    Runs the complete end-to-end pipeline with consistency mechanisms:
      - Document fingerprint caching for repeat analysis
      - Multi-run consensus for deterministic LLM output
      - Blended scoring (rule-based + LLM-based) for stable scores
    """
    contract_name = os.path.basename(file_path)
    log = PipelineLogger(contract_name)
    
    print(f"\nStarting ClauseGuard review for: {contract_name}")
    print("-" * 50)
    
    # 1. Ingestion
    log.step_start("1/7 Ingestion", f"Loading {contract_name}")
    ingestion_result = IngestionPipeline().process(file_path)
    if ingestion_result["status"] != "SUCCESS":
        log.log_error("Ingestion", RuntimeError(ingestion_result.get('error', 'Unknown error')))
        return
    parsed_text = ingestion_result["parsed_text"]
    log.step_end(details=f"parsed {len(parsed_text)} chars")
    
    # 1b. Cache check
    cache = DocumentCache()
    if use_cache:
        log.step_start("1b/7 Cache Check", "Looking for previous analysis")
        cached = cache.get(parsed_text)
        if cached:
            log.step_end(details="CACHE HIT — returning cached results")
            print("\n⚡ Returning cached results (identical to previous analysis)")
            log.pipeline_summary(cached["score"], len(cached["findings"]))
            return cached
        log.step_end(details="CACHE MISS — running full pipeline")
    
    # 2. LLM Analysis (with optional consensus)
    analyzer = StructuredAnalyzer()
    if use_consensus:
        log.step_start("2/7 Consensus Analysis", "Running analyzer 3x and voting")
        consensus = ConsensusAnalyzer(num_runs=3, min_consensus=2)
        consensus_result = await consensus.analyze_with_consensus(analyzer, parsed_text)
        raw_findings = consensus_result["findings"]
        meta = consensus_result["consensus_metadata"]
        log.step_end(finding_count=len(raw_findings),
                     details=f"{meta['successful_runs']}/{meta['num_runs']} runs succeeded, "
                             f"{meta['total_raw_findings']} raw → {meta['consensus_findings']} consensus")
        log.log_findings("Raw LLM Output (consensus)", raw_findings)
    else:
        log.step_start("2/7 Analysis", "Extracting structured risks via LLM (single run)")
        analyzer_result = await analyzer.analyze(parsed_text)
        raw_findings = analyzer_result.get("findings", [])
        log.step_end(finding_count=len(raw_findings))
        log.log_findings("Raw LLM Output", raw_findings)
    
    # 3. Deduplication
    log.step_start("3/7 Deduplication", "Removing overlapping findings")
    deduped = FindingsDeduplicator().deduplicate(raw_findings)
    log.step_end(finding_count=len(deduped))
    log.log_dropped("Deduplication", len(raw_findings), len(deduped))
    
    # 4. Deterministic Verification
    log.step_start("4/7 Verification", "Schema + Grounding + Confidence checks")
    det_verified = DeterministicVerifier().verify(deduped, parsed_text)
    log.step_end(finding_count=len(det_verified))
    log.log_dropped("Deterministic Verification", len(deduped), len(det_verified))
    
    # 5. Semantic Verification
    log.step_start("5/7 Semantic Check", "LLM-based legal interpretation verification")
    sem_verified = await SemanticVerifier().verify_interpretation(det_verified, contract_text=parsed_text)
    log.step_end(finding_count=len(sem_verified))
    log.log_dropped("Semantic Verification", len(det_verified), len(sem_verified))
    log.log_findings("Final Verified Findings", sem_verified)
    
    # 6. Synthesis
    log.step_start("6/7 Synthesis", "Generating markdown report")
    final_report = await ReportSynthesizer().generate_report(sem_verified)
    log.step_end()
    
    # 7. Blended Scoring (rule-based + LLM-based)
    log.step_start("7/7 Blended Score", "Combining rule-based and LLM-based scores")
    blended = BlendedScorer(alpha=0.6)
    score, score_breakdown = blended.calculate_score(sem_verified, parsed_text)
    log.step_end(details=f"score={score}/100 (LLM={score_breakdown['llm_score']}, rules={score_breakdown['rule_score']})")
    log.log_score(score, score_breakdown)
    
    # Final Output
    print("\n" + "=" * 60)
    print(" FINAL CLAUSEGUARD REPORT")
    print(f" SAFETY SCORE: {score}/100")
    print(f" (LLM: {score_breakdown['llm_score']}, Rules: {score_breakdown['rule_score']})")
    print("=" * 60)
    print(final_report)
    
    log.pipeline_summary(score, len(sem_verified))
    
    # Cache the results for future runs
    if use_cache:
        result_data = {
            "report": final_report,
            "findings": sem_verified,
            "score": score,
            "score_breakdown": score_breakdown,
            "contract_text": parsed_text,
            "metrics": log.get_metrics(),
        }
        cache.set(parsed_text, result_data)
        print("\n📦 Results cached for future runs.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m src.main <path_to_contract_file>")
        sys.exit(1)
        
    contract_path = sys.argv[1]
    asyncio.run(run_clauseguard(contract_path))