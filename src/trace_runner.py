"""
ClauseGuard — Agent Trajectory Capture Script

Runs the full pipeline against sow_003_risky.txt (the adversarial contract)
with rich, step-by-step logging. Captures:
  - Every agent's system prompt excerpt
  - Raw LLM outputs
  - Verification decisions per finding
  - Retry events
  - Final pipeline summary with timings

Output: TRAJECTORY_LOG.json  (machine-readable)
        TRAJECTORY_LOG.txt   (human-readable, for submission)

Usage:
    python -m src.trace_runner
"""

import asyncio
import json
import os
import sys
import time
from datetime import datetime, timezone
from typing import Optional

# Ensure UTF-8 output on Windows
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except AttributeError:
    pass


# ── Trace Event Model ─────────────────────────────────────────────────────────

def make_event(
    agent: str,
    event_type: str,
    content: object,
    elapsed: Optional[float] = None,
    outcome: Optional[str] = None,
) -> dict:
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "agent": agent,
        "event": event_type,
        "elapsed_s": round(elapsed, 3) if elapsed is not None else None,
        "outcome": outcome,
        "content": content,
    }


# ── Instrumented Pipeline ─────────────────────────────────────────────────────

async def run_traced_pipeline(contract_path: str) -> dict:
    """
    Runs the full ClauseGuard pipeline against a contract file,
    capturing a rich trace of every agent's inputs, outputs, decisions,
    and retries.
    """
    from .ingestion import IngestionPipeline
    from .analyzer import StructuredAnalyzer
    from .consensus import ConsensusAnalyzer
    from .deduplicator import FindingsDeduplicator
    from .verifier import DeterministicVerifier
    from .semantic_verifier import SemanticVerifier
    from .synthesizer import ReportSynthesizer
    from .blended_scorer import BlendedScorer
    from .llm import get_model

    trace = {
        "run_id": f"trace_{int(time.time())}",
        "contract": os.path.basename(contract_path),
        "started_at": datetime.now(timezone.utc).isoformat(),
        "events": [],
        "summary": {},
    }

    def log(event: dict):
        trace["events"].append(event)
        icon = {
            "STEP_START": "▶",
            "LLM_CALL": "🤖",
            "LLM_RESPONSE": "📥",
            "DECISION": "✅" if event.get("outcome") == "PASS" else ("❌" if event.get("outcome") == "FAIL" else "⚖"),
            "RETRY": "🔄",
            "CACHE": "💾",
            "DROP": "🗑",
            "KEEP": "✅",
            "SUMMARY": "📊",
            "ERROR": "❌",
        }.get(event["event"], "•")
        print(f"  {icon} [{event['agent']}] {event['event']}: ", end="")
        c = event.get("content")
        if isinstance(c, str):
            print(c[:120] + ("..." if len(c) > 120 else ""))
        elif isinstance(c, dict):
            print(json.dumps(c, ensure_ascii=False)[:200])
        else:
            print(str(c)[:120])

    pipeline_start = time.time()

    # ── AGENT 1: Ingestion ────────────────────────────────────────────────────
    print("\n" + "═" * 70)
    print("  AGENT 1: IngestionPipeline")
    print("═" * 70)

    t0 = time.time()
    log(make_event("IngestionPipeline", "STEP_START", {
        "action": "Parse contract file to raw text",
        "file": os.path.basename(contract_path),
        "supported_formats": [".pdf", ".docx", ".txt"],
    }))

    ingestion = IngestionPipeline()
    ingest_result = ingestion.process(contract_path)

    elapsed = time.time() - t0
    if ingest_result["status"] == "SUCCESS":
        text = ingest_result["parsed_text"]
        log(make_event("IngestionPipeline", "DECISION", {
            "status": "SUCCESS",
            "file_hash_sha256": ingest_result["file_hash"][:16] + "...",
            "chars_extracted": len(text),
            "first_100_chars": text[:100],
        }, elapsed=elapsed, outcome="PASS"))
    else:
        log(make_event("IngestionPipeline", "ERROR", ingest_result.get("error"), elapsed=elapsed, outcome="FAIL"))
        raise RuntimeError(f"Ingestion failed: {ingest_result['error']}")

    parsed_text = ingest_result["parsed_text"]

    # ── AGENT 2: Consensus Analyzer (3× StructuredAnalyzer) ──────────────────
    print("\n" + "═" * 70)
    print("  AGENT 2: ConsensusAnalyzer + StructuredAnalyzer × 3")
    print("═" * 70)

    log(make_event("ConsensusAnalyzer", "STEP_START", {
        "action": "Run StructuredAnalyzer concurrently 3×",
        "num_runs": 3,
        "min_consensus": 2,
        "strategy": "Majority vote on (clause_ref, category) signature",
        "model": get_model("analysis"),
        "temperature": 0.0,
        "system_prompt_excerpt": (
            "You are ClauseGuard, an expert legal AI specializing in protecting freelancers "
            "from risky contract clauses. Your ONLY job is to analyze the contract text for "
            "risks and output STRICT, VALID JSON... [see src/analyzer.py for full prompt]"
        ),
    }))

    t0 = time.time()

    # Run consensus (internally fires 3 concurrent LLM calls)
    analyzer = StructuredAnalyzer()
    consensus = ConsensusAnalyzer(num_runs=3, min_consensus=2)

    # Monkey-patch analyzer to capture individual run outputs
    original_analyze = analyzer.analyze
    run_outputs = []

    async def traced_analyze(contract_text: str) -> dict:
        run_start = time.time()
        run_num = len(run_outputs) + 1
        log(make_event("StructuredAnalyzer", "LLM_CALL", {
            "run": f"{run_num}/3",
            "model": get_model("analysis"),
            "temperature": 0.0,
            "input_chars": len(contract_text),
        }))
        try:
            result = await original_analyze(contract_text)
            run_time = time.time() - run_start
            run_outputs.append(result)
            count = len(result.get("findings", []))
            log(make_event("StructuredAnalyzer", "LLM_RESPONSE", {
                "run": f"{run_num}/3",
                "findings_returned": count,
                "categories_found": list({f.get("category") for f in result.get("findings", [])}),
                "elapsed_s": round(run_time, 2),
            }, elapsed=run_time, outcome="PASS"))
            return result
        except Exception as e:
            run_time = time.time() - run_start
            log(make_event("StructuredAnalyzer", "ERROR", {
                "run": f"{run_num}/3", "error": str(e)
            }, elapsed=run_time, outcome="FAIL"))
            raise

    analyzer.analyze = traced_analyze
    consensus_result = await consensus.analyze_with_consensus(analyzer, parsed_text)
    consensus_elapsed = time.time() - t0

    meta = consensus_result["consensus_metadata"]
    raw_findings = consensus_result["findings"]

    log(make_event("ConsensusAnalyzer", "DECISION", {
        "successful_runs": meta["successful_runs"],
        "total_raw_findings_across_runs": meta["total_raw_findings"],
        "consensus_findings_survived": meta["consensus_findings"],
        "dropped_as_non_consensus": meta["dropped_findings"],
        "consensus_rule": f"Must appear in >= {meta['min_consensus']}/{meta['num_runs']} runs",
        "note": "Findings that appeared in only 1/3 runs are classified as transient hallucinations and dropped",
    }, elapsed=consensus_elapsed, outcome="PASS"))

    for f in raw_findings:
        log(make_event("ConsensusAnalyzer", "KEEP", {
            "clause_ref": f.get("clause_ref"),
            "category": f.get("category"),
            "severity": f.get("severity"),
            "confidence": f.get("confidence"),
            "consensus_runs": f.get("consensus_runs"),
        }))

    # ── AGENT 3: Deduplicator ─────────────────────────────────────────────────
    print("\n" + "═" * 70)
    print("  AGENT 3: FindingsDeduplicator")
    print("═" * 70)

    t0 = time.time()
    log(make_event("FindingsDeduplicator", "STEP_START", {
        "action": "Merge findings with >80% quote overlap or identical (clause_ref, category)",
        "strategy": "Keep highest-confidence version of each duplicate group",
        "quote_overlap_threshold": "80%",
        "input_count": len(raw_findings),
    }))

    deduped = FindingsDeduplicator().deduplicate(raw_findings)
    dedup_elapsed = time.time() - t0

    dropped = len(raw_findings) - len(deduped)
    log(make_event("FindingsDeduplicator", "DECISION", {
        "input": len(raw_findings),
        "output": len(deduped),
        "duplicates_merged": dropped,
        "elapsed_s": round(dedup_elapsed, 3),
    }, elapsed=dedup_elapsed, outcome="PASS"))

    # ── AGENT 4: DeterministicVerifier ───────────────────────────────────────
    print("\n" + "═" * 70)
    print("  AGENT 4: DeterministicVerifier (4-Point Grounding Check)")
    print("═" * 70)

    t0 = time.time()
    log(make_event("DeterministicVerifier", "STEP_START", {
        "action": "4-point programmatic grounding check — no LLM involved",
        "checks": [
            "1. Schema: All required fields present and non-empty",
            "2. Values: severity ∈ {must_raise, worth_raising}; category ∈ 6 valid values",
            "3. Grounding: quote exists verbatim in source text (or ≥60% word overlap)",
            "4. Confidence: confidence >= 0.5",
        ],
        "kill_switch": "ALL checks must pass — single failure drops the finding",
        "input_count": len(deduped),
    }))

    verifier = DeterministicVerifier()
    det_verified = verifier.verify(deduped, parsed_text)
    det_elapsed = time.time() - t0

    for f in deduped:
        checks = f.get("verification_checks", {})
        passed = all(v == "PASS" or v.startswith("PASS ") for v in checks.values())
        outcome = "PASS" if passed else "FAIL"
        evt = "KEEP" if passed else "DROP"
        log(make_event("DeterministicVerifier", evt, {
            "clause_ref": f.get("clause_ref"),
            "category": f.get("category"),
            "checks": checks,
        }, outcome=outcome))

    log(make_event("DeterministicVerifier", "DECISION", {
        "input": len(deduped),
        "survived": len(det_verified),
        "dropped": len(deduped) - len(det_verified),
        "elapsed_s": round(det_elapsed, 3),
    }, elapsed=det_elapsed, outcome="PASS"))

    # ── AGENT 5: SemanticVerifier ─────────────────────────────────────────────
    print("\n" + "═" * 70)
    print("  AGENT 5: SemanticVerifier (LLM-as-Judge)")
    print("═" * 70)

    log(make_event("SemanticVerifier", "STEP_START", {
        "action": "Independent LLM judge evaluates whether each finding's explanation matches its quote in full context",
        "model": get_model("verification"),
        "temperature": 0.0,
        "batch_size": 3,
        "batch_delay_s": 2.0,
        "verdicts": {
            "YES": "Finding is confirmed — keep",
            "UNCERTAIN": "Borderline — keep with uncertainty tag",
            "NO": "Finding is rejected — drop",
        },
        "fail_open_policy": "On API error after 3 retries, keep as UNCERTAIN (grounding already confirmed quote exists)",
        "system_prompt_excerpt": (
            "You are a strict legal verification AI specializing in freelancer contract risk analysis. "
            "Your ONLY job is to determine whether a quoted contract clause actually represents the claimed risk... "
            "[see src/semantic_verifier.py for full prompt]"
        ),
        "input_count": len(det_verified),
    }))

    t0 = time.time()

    # Monkey-patch to capture per-finding verdicts
    sem_verifier = SemanticVerifier()
    original_verify_single = sem_verifier._verify_single

    async def traced_verify_single(finding: dict, contract_text: str = "") -> Optional[dict]:
        f_start = time.time()
        log(make_event("SemanticVerifier", "LLM_CALL", {
            "clause_ref": finding.get("clause_ref"),
            "category": finding.get("category"),
            "quote_preview": finding.get("quote", "")[:80] + "...",
            "model": get_model("verification"),
        }))
        result = await original_verify_single(finding, contract_text)
        f_elapsed = time.time() - f_start
        verdict = finding.get("semantic_check", {}).get("verdict", "DROPPED")
        reason = finding.get("semantic_check", {}).get("reason", "N/A")
        outcome_str = "PASS" if result is not None else "FAIL"
        log(make_event("SemanticVerifier", "KEEP" if result is not None else "DROP", {
            "clause_ref": finding.get("clause_ref"),
            "category": finding.get("category"),
            "verdict": verdict,
            "reason": reason,
            "elapsed_s": round(f_elapsed, 2),
        }, elapsed=f_elapsed, outcome=outcome_str))
        return result

    sem_verifier._verify_single = traced_verify_single
    sem_verified = await sem_verifier.verify_interpretation(det_verified, contract_text=parsed_text)
    sem_elapsed = time.time() - t0

    log(make_event("SemanticVerifier", "DECISION", {
        "input": len(det_verified),
        "survived": len(sem_verified),
        "dropped": len(det_verified) - len(sem_verified),
        "elapsed_s": round(sem_elapsed, 2),
    }, elapsed=sem_elapsed, outcome="PASS"))

    # ── AGENT 6: ReportSynthesizer + BlendedScorer ────────────────────────────
    print("\n" + "═" * 70)
    print("  AGENT 6: ReportSynthesizer + BlendedScorer")
    print("═" * 70)

    log(make_event("ReportSynthesizer", "STEP_START", {
        "action": "Compile verified findings into Markdown report",
        "input_findings": len(sem_verified),
    }))
    t0 = time.time()
    report = await ReportSynthesizer().generate_report(sem_verified)
    synth_elapsed = time.time() - t0
    log(make_event("ReportSynthesizer", "DECISION", {
        "report_chars": len(report),
        "elapsed_s": round(synth_elapsed, 2),
    }, elapsed=synth_elapsed, outcome="PASS"))

    log(make_event("BlendedScorer", "STEP_START", {
        "action": "Compute blended safety score",
        "formula": "score = 0.6 × rule_score + 0.4 × llm_score",
        "alpha": 0.6,
        "rule_component": "Deterministic regex scanner (Net-30, kill fee, liability cap, etc.)",
        "llm_component": "Weighted severity scoring with diminishing returns per category",
    }))
    t0 = time.time()
    score, breakdown = BlendedScorer(alpha=0.6).calculate_score(sem_verified, parsed_text)
    score_elapsed = time.time() - t0
    log(make_event("BlendedScorer", "DECISION", {
        "final_score": score,
        "rule_score": breakdown["rule_score"],
        "llm_score": breakdown["llm_score"],
        "formula": breakdown["blending_formula"],
        "stability_band": breakdown["stability_band"],
        "elapsed_s": round(score_elapsed, 3),
    }, elapsed=score_elapsed, outcome="PASS"))

    # ── Pipeline Summary ──────────────────────────────────────────────────────
    total_elapsed = time.time() - pipeline_start

    trace["summary"] = {
        "total_elapsed_s": round(total_elapsed, 2),
        "final_score": score,
        "final_findings": len(sem_verified),
        "pipeline_funnel": {
            "after_consensus": len(raw_findings),
            "after_dedup": len(deduped),
            "after_deterministic_verify": len(det_verified),
            "after_semantic_verify": len(sem_verified),
        },
        "score_breakdown": breakdown,
    }

    log(make_event("Pipeline", "SUMMARY", {
        "total_elapsed_s": round(total_elapsed, 2),
        "final_safety_score": f"{score}/100",
        "final_findings": len(sem_verified),
        "funnel": trace["summary"]["pipeline_funnel"],
    }))

    return trace


# ── Runner ────────────────────────────────────────────────────────────────────

async def main():
    contract = os.path.join(os.path.dirname(__file__), "../contracts/sow_003_risky.txt")
    output_dir = os.path.join(os.path.dirname(__file__), "../data")

    print("\n" + "█" * 70)
    print("  ClauseGuard — Agent Trajectory Capture")
    print("  Contract: sow_003_risky.txt (adversarial test contract)")
    print("█" * 70)

    try:
        trace = await run_traced_pipeline(contract)

        # Save JSON trace
        json_path = os.path.join(output_dir, "TRAJECTORY_LOG.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(trace, f, indent=2, ensure_ascii=False)

        print(f"\n✅ Trace saved → {json_path}")
        print(f"\n{'█' * 70}")
        print(f"  PIPELINE COMPLETE")
        print(f"  Final Safety Score : {trace['summary']['final_score']}/100")
        print(f"  Final Findings     : {trace['summary']['final_findings']}")
        print(f"  Total Runtime      : {trace['summary']['total_elapsed_s']}s")
        print(f"  Events Captured    : {len(trace['events'])}")
        print(f"{'█' * 70}\n")

    except Exception as e:
        print(f"\n❌ Trajectory capture failed: {type(e).__name__}: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
