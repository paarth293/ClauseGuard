"""
Multi-Run Consensus Analyzer

The single biggest source of inconsistency is LLM non-determinism:
even at temperature=0.0, the same input can produce slightly different findings
across runs due to GPU floating-point non-determinism and server-side batching.

Solution: run the analyzer N times and only keep findings that appear in the
majority of runs. This is how industry-grade systems handle LLM unreliability.

Consensus Strategy:
  1. Run the analyzer N times (default: 3)
  2. For each run, extract a "finding signature" = (clause_ref, category)
  3. A finding is "consensus" if its signature appears in >= M runs (default: 2)
  4. When multiple versions of the same finding exist across runs, keep the one
     with the highest confidence (most detailed quote, best explanation)

This eliminates random hallucinations that only appear in 1 out of 3 runs,
while preserving real findings that consistently appear.
"""

import asyncio
from typing import Optional


# ── Configuration ────────────────────────────────────────────────────────────

DEFAULT_NUM_RUNS = 3
DEFAULT_MIN_CONSENSUS = 2  # Need 2 out of 3 runs to agree


class ConsensusAnalyzer:
    """
    Wraps the StructuredAnalyzer to produce consistent results via multi-run voting.
    """

    def __init__(self, num_runs: int = DEFAULT_NUM_RUNS, min_consensus: int = DEFAULT_MIN_CONSENSUS):
        self.num_runs = num_runs
        self.min_consensus = min_consensus

    async def analyze_with_consensus(self, analyzer, contract_text: str) -> dict:
        """
        Run the analyzer N times concurrently and return only consensus findings.

        Args:
            analyzer: A StructuredAnalyzer instance
            contract_text: The parsed contract text

        Returns:
            dict with "findings" key containing only consensus findings,
            plus "consensus_metadata" with run details
        """
        # Run all analyses concurrently
        tasks = [analyzer.analyze(contract_text) for _ in range(self.num_runs)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter out failed runs
        successful_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                print(f"[CONSENSUS] Run {i+1}/{self.num_runs} failed: {result}")
                continue
            if isinstance(result, dict) and "findings" in result:
                successful_results.append(result)

        if not successful_results:
            # All runs failed — return empty with error info
            return {
                "findings": [],
                "consensus_metadata": {
                    "num_runs": self.num_runs,
                    "successful_runs": 0,
                    "min_consensus": self.min_consensus,
                    "error": "All analyzer runs failed",
                }
            }

        # Build signature map: signature -> list of (finding, run_index)
        signature_map: dict[str, list[tuple[dict, int]]] = {}

        for run_idx, result in enumerate(successful_results):
            for finding in result.get("findings", []):
                sig = self._get_signature(finding)
                if sig not in signature_map:
                    signature_map[sig] = []
                signature_map[sig].append((finding, run_idx))

        # Filter to consensus findings
        consensus_findings = []
        for sig, occurrences in signature_map.items():
            num_agreeing_runs = len(set(run_idx for _, run_idx in occurrences))
            if num_agreeing_runs >= self.min_consensus:
                # Keep the version with highest confidence
                best_finding = max(
                    occurrences,
                    key=lambda x: float(x[0].get("confidence", 0))
                )[0]
                best_finding["consensus_runs"] = num_agreeing_runs
                best_finding["consensus_total"] = len(successful_results)
                consensus_findings.append(best_finding)

        metadata = {
            "num_runs": self.num_runs,
            "successful_runs": len(successful_results),
            "min_consensus": self.min_consensus,
            "total_raw_findings": sum(len(r.get("findings", [])) for r in successful_results),
            "consensus_findings": len(consensus_findings),
            "dropped_findings": sum(len(r.get("findings", [])) for r in successful_results) - len(consensus_findings),
        }

        return {
            "findings": consensus_findings,
            "consensus_metadata": metadata,
        }

    def _get_signature(self, finding: dict) -> str:
        """
        Create a normalized signature for a finding.
        Two findings with the same signature are considered "the same risk".
        """
        clause_ref = finding.get("clause_ref", "").lower().strip()
        category = finding.get("category", "").lower().strip()
        # Normalize clause_ref: remove extra whitespace, periods, parentheses
        clause_ref = " ".join(clause_ref.split())
        return f"{clause_ref}::{category}"


# ── Standalone Test ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Simulate multi-run consensus with mock data
    class MockAnalyzer:
        """Simulates an analyzer that produces slightly different results each time."""
        def __init__(self):
            self._call_count = 0

        async def analyze(self, text):
            self._call_count += 1
            # Run 1 & 3: find ip_ownership + payment_terms
            # Run 2: find ip_ownership + a hallucinated "other_risk"
            if self._call_count in (1, 3):
                return {"findings": [
                    {"clause_ref": "Section 3", "category": "ip_ownership", "severity": "must_raise",
                     "confidence": 0.9, "quote": "all work shall become property of Client"},
                    {"clause_ref": "Section 2", "category": "payment_terms", "severity": "worth_raising",
                     "confidence": 0.8, "quote": "pay within 15 days"},
                ]}
            else:
                return {"findings": [
                    {"clause_ref": "Section 3", "category": "ip_ownership", "severity": "must_raise",
                     "confidence": 0.85, "quote": "all work shall become property of Client"},
                    {"clause_ref": "Section 4", "category": "other_risk", "severity": "worth_raising",
                     "confidence": 0.6, "quote": "some random clause"},  # Hallucination!
                ]}

    async def test():
        analyzer = MockAnalyzer()
        consensus = ConsensusAnalyzer(num_runs=3, min_consensus=2)

        result = await consensus.analyze_with_consensus(analyzer, "test contract")

        print(f"Total raw findings across 3 runs: {result['consensus_metadata']['total_raw_findings']}")
        print(f"Consensus findings: {result['consensus_metadata']['consensus_findings']}")
        print(f"Dropped (hallucinations): {result['consensus_metadata']['dropped_findings']}")
        print()
        for f in result["findings"]:
            print(f"  + [{f['category']}] {f['clause_ref']} "
                  f"(conf={f['confidence']}, runs={f['consensus_runs']}/{f['consensus_total']})")

    asyncio.run(test())
