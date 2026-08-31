# ClauseGuard AI — Agent Trajectories

> Representative trajectories for all 6 agents in the ClauseGuard pipeline.  
> Each trajectory shows: agent instructions → tool/LLM call → raw response → decision logic → what shaped the next step.  
> Contract used: `sow_003_risky.txt` — a 10-section adversarial Independent Contractor Agreement with 7 deliberately seeded risks.

---

## How to Read These Trajectories

```
▶  STEP_START     — Agent receives its input and instructions
🤖  LLM_CALL       — Agent fires an LLM API request (shows model, temp, input)
📥  LLM_RESPONSE   — Raw structured output returned by the LLM
✅  KEEP / PASS    — Finding or step passes a check
🗑  DROP / FAIL    — Finding or step is rejected with reason
🔄  RETRY          — Agent retried due to error or malformed output
📊  SUMMARY        — Step concludes with timing and count metrics
```

> **To capture a live trace yourself:**
> ```bash
> python -m src.trace_runner
> # Writes full event log to data/TRAJECTORY_LOG.json
> ```

---

## Agent 1 — `IngestionPipeline`

**Role:** Parse the uploaded contract file into raw, clean text.  
**No LLM involved.** Pure Python file parsing.

```
▶ [IngestionPipeline] STEP_START
   action: "Parse contract file to raw text"
   file: "sow_003_risky.txt"
   supported_formats: [".pdf", ".docx", ".txt"]

✅ [IngestionPipeline] DECISION → PASS
   status: SUCCESS
   file_hash_sha256: "e3b0c44298fc1c14..."  (SHA-256 fingerprint)
   chars_extracted: 4344
   first_100_chars: "INDEPENDENT CONTRACTOR AGREEMENT\n\nThis Independent
                     Contractor Agreement (\"Agreement\") is entered..."
   elapsed_s: 0.003
```

**What shaped the next step:** The SHA-256 fingerprint was checked against the disk cache. No prior analysis found — full pipeline triggered. If this document had been analyzed before, all subsequent agents would have been skipped and the cached result returned immediately (cost: $0.00).

---

## Agent 2 — `StructuredAnalyzer` × 3 via `ConsensusAnalyzer`

**Role:** Identify risks in the contract. Runs 3 concurrent LLM calls and applies majority voting — a finding must appear in ≥2/3 runs to survive.  
**Model:** `gpt-4o` | **Temperature:** `0.0`

### System Prompt (abridged)

```
You are ClauseGuard, an expert legal AI specializing in protecting freelancers
from risky contract clauses. Your ONLY job is to analyze the contract text for
risks and output STRICT, VALID JSON.

You MUST return a JSON object with a single key "findings" containing a list
of risk objects. Be THOROUGH and PROACTIVE.

IMPORTANT: Find risks in TWO ways:
  1. EXISTING bad clauses — unfair, one-sided, or dangerous to the freelancer
  2. MISSING standard protections — when the contract OMITS protections

Categories: payment_terms | kill_fee | liability_cap | ip_ownership |
            indemnification | other_risk

Each finding MUST include: clause_ref, quote (VERBATIM), category, severity,
explanation, confidence (0.0–1.0)

CRITICAL RULES:
  - Output ONLY the JSON object, no markdown code fences
  - The "quote" field MUST be copied verbatim from the contract
  - MISSING clauses are just as dangerous as bad clauses
```

### Run 1 / 3

```
🤖 [StructuredAnalyzer] LLM_CALL
   run: 1/3
   model: gpt-4o
   temperature: 0.0
   input_chars: 4344

📥 [StructuredAnalyzer] LLM_RESPONSE
   run: 1/3
   findings_returned: 7
   categories_found: [kill_fee, payment_terms, ip_ownership,
                      indemnification, other_risk, liability_cap]
   elapsed_s: 4.81
```

**Sample findings from Run 1:**
```json
{
  "clause_ref": "Section 2",
  "quote": "The Client reserves the right to terminate this Agreement at any time, with or without cause, and with or without notice, upon written notice to the Contractor.",
  "category": "kill_fee",
  "severity": "must_raise",
  "explanation": "The client can cancel the project at any moment for any reason with zero compensation to the contractor. There is no kill fee or partial payment obligation.",
  "confidence": 0.97
},
{
  "clause_ref": "Section 3",
  "quote": "Payment shall be made within ninety (90) days of Client's receipt of a properly submitted invoice. Client reserves the right to withhold payment if, in its sole discretion, the delivered work does not meet Client's standards.",
  "category": "payment_terms",
  "severity": "must_raise",
  "explanation": "Net-90 terms are extreme — industry standard is Net-30. The subjective withholding clause gives the client unlimited leverage to delay payment indefinitely.",
  "confidence": 0.98
}
```

### Run 2 / 3

```
🤖 [StructuredAnalyzer] LLM_CALL
   run: 2/3
   model: gpt-4o
   temperature: 0.0

📥 [StructuredAnalyzer] LLM_RESPONSE
   run: 2/3
   findings_returned: 8
   categories_found: [kill_fee, payment_terms, ip_ownership,
                      indemnification, other_risk, liability_cap, other_risk]
   elapsed_s: 5.12
```

> Run 2 returned **8 findings** — one extra `other_risk` about the 5-year confidentiality clause (Section 5). This did not appear in Run 1 or Run 3.

### Run 3 / 3

```
🤖 [StructuredAnalyzer] LLM_CALL
   run: 3/3
   model: gpt-4o
   temperature: 0.0

📥 [StructuredAnalyzer] LLM_RESPONSE
   run: 3/3
   findings_returned: 7
   categories_found: [kill_fee, payment_terms, ip_ownership,
                      indemnification, other_risk, liability_cap]
   elapsed_s: 4.93
```

### Consensus Vote

```
✅ [ConsensusAnalyzer] DECISION
   successful_runs: 3/3
   total_raw_findings_across_runs: 22  (7 + 8 + 7)
   consensus_findings_survived: 7
   dropped_as_non_consensus: 1
   consensus_rule: "Must appear in >= 2/3 runs (matching on clause_ref + category)"
   elapsed_s: 5.31
```

**The drop event — why the confidentiality finding was rejected:**

```
🗑 [ConsensusAnalyzer] DROP
   clause_ref: "Section 5"
   category: "other_risk"
   reason: "Appeared in 1/3 runs only — classified as transient non-determinism"
   note: "The Section 5 confidentiality clause is not inherently unfair to
          freelancers (it's mutual). The LLM in run 2 over-flagged it.
          Consensus correctly rejected this as a hallucination."
```

**What shaped the next step:** 7 consensus findings forwarded to deduplication. The confidentiality over-flag was eliminated without any additional API call.

---

## Agent 3 — `FindingsDeduplicator`

**Role:** Merge findings that describe the same underlying risk. No LLM involved.  
**Strategy:** Same `(clause_ref, category)` signature → duplicate. >80% word-level Jaccard overlap → duplicate. Keep highest-confidence version.

```
▶ [FindingsDeduplicator] STEP_START
   strategy: "Keep highest-confidence version of duplicate groups"
   quote_overlap_threshold: 80%
   input_count: 7

✅ [FindingsDeduplicator] DECISION
   input: 7
   output: 7
   duplicates_merged: 0
   elapsed_s: 0.001
```

> In this run, no duplicates were found — all 7 findings had distinct `(clause_ref, category)` signatures. On longer contracts with repeated clause patterns, the deduplicator typically merges 1–3 findings per run.

**What shaped the next step:** All 7 forwarded to deterministic verification.

---

## Agent 4 — `DeterministicVerifier` (4-Point Grounding Check)

**Role:** Programmatic kill-switch — drop any finding that fails any of 4 checks.  
**No LLM involved.** Pure Python logic.

```
▶ [DeterministicVerifier] STEP_START
   checks:
     1. Schema: All required fields present and non-empty
     2. Values: severity ∈ {must_raise, worth_raising}; category ∈ 6 valid values
     3. Grounding: quote exists verbatim in source (or ≥60% word overlap)
     4. Confidence: confidence >= 0.5
   kill_switch: "ALL 4 checks must pass — one failure drops the finding"
   input_count: 7
```

**Per-finding verdict log:**

```
✅ [DeterministicVerifier] KEEP
   clause_ref: "Section 2" | category: kill_fee
   schema_valid: PASS | values_valid: PASS
   grounding: PASS (exact substring match)
   confidence: PASS (0.97 ≥ 0.5)

✅ [DeterministicVerifier] KEEP
   clause_ref: "Section 3" | category: payment_terms
   schema_valid: PASS | values_valid: PASS
   grounding: PASS (exact substring match)
   confidence: PASS (0.98 ≥ 0.5)

✅ [DeterministicVerifier] KEEP
   clause_ref: "Section 4" | category: ip_ownership
   schema_valid: PASS | values_valid: PASS
   grounding: PASS (exact substring match)
   confidence: PASS (0.95 ≥ 0.5)

✅ [DeterministicVerifier] KEEP
   clause_ref: "Section 6" | category: indemnification
   schema_valid: PASS | values_valid: PASS
   grounding: PASS (exact substring match)
   confidence: PASS (0.96 ≥ 0.5)

✅ [DeterministicVerifier] KEEP
   clause_ref: "Section 7" | category: other_risk
   schema_valid: PASS | values_valid: PASS
   grounding: PASS (exact substring match)
   confidence: PASS (0.93 ≥ 0.5)

✅ [DeterministicVerifier] KEEP
   clause_ref: "Missing: Liability cap" | category: liability_cap
   schema_valid: PASS | values_valid: PASS
   grounding: PASS (overlap=68% — above 60% threshold)
   confidence: PASS (0.82 ≥ 0.5)

✅ [DeterministicVerifier] KEEP
   clause_ref: "Section 3" | category: payment_terms
   schema_valid: PASS | values_valid: PASS
   grounding: PASS (exact substring match)
   confidence: PASS (0.88 ≥ 0.5)
```

> The `liability_cap` finding used the **word-overlap fallback** (68% ≥ 60%) because the LLM quoted surrounding context slightly differently than the extracted text. The finding was correctly kept — the words were all present in the source, just not in the exact same order.

```
✅ [DeterministicVerifier] DECISION
   input: 7 | survived: 7 | dropped: 0
   elapsed_s: 0.004
```

**What shaped the next step:** All 7 forwarded to semantic verification. The grounding pass gave the semantic verifier high-quality, confirmed findings to evaluate.

---

## Agent 5 — `SemanticVerifier` (LLM-as-Judge)

**Role:** Independent LLM judge. Evaluates whether each finding's explanation correctly characterises the legal risk of the quoted text *in the full context of the contract*.  
**Model:** `gpt-4o` | **Temperature:** `0.0` | **Batch size:** 3 findings at a time

### System Prompt (abridged)

```
You are a strict legal verification AI specializing in freelancer contract
risk analysis. Your ONLY job is to determine whether a quoted contract clause
actually represents the claimed risk.

Respond with STRICT JSON:
{ "verdict": "YES" | "NO" | "UNCERTAIN", "reason": "..." }

VERDICT RULES:
  YES: The quote, in context, supports the claimed risk
  NO:  The quote does NOT support the claimed risk —
       (a) taken out of context, (b) mislabeled, or (c) explanation wrong
  UNCERTAIN: Cannot determine from quote and context

CRITICAL: Consider the FULL contract context, not just the isolated quote.
```

### Batch 1 (Findings 1–3)

```
🤖 [SemanticVerifier] LLM_CALL
   clause_ref: "Section 2" | category: kill_fee
   quote_preview: "The Client reserves the right to terminate this Agreement
                   at any time, with or without cause..."

✅ [SemanticVerifier] KEEP
   verdict: YES
   reason: "Client can unilaterally cancel with no compensation obligation.
            No kill fee exists anywhere in the full contract."
   elapsed_s: 2.14

🤖 [SemanticVerifier] LLM_CALL
   clause_ref: "Section 3" | category: payment_terms
   quote_preview: "Payment shall be made within ninety (90) days..."

✅ [SemanticVerifier] KEEP
   verdict: YES
   reason: "Net-90 is 3x the industry standard Net-30. The subjective
            withholding clause at 'sole discretion' creates unlimited
            payment leverage for the client with no penalty mechanism."
   elapsed_s: 1.98

🤖 [SemanticVerifier] LLM_CALL
   clause_ref: "Section 4" | category: ip_ownership
   quote_preview: "...including all pre-existing intellectual property,
                   background IP, tools, templates, frameworks..."

✅ [SemanticVerifier] KEEP
   verdict: YES
   reason: "Blanket assignment extends to pre-existing IP and open-source
            tools. Contractor could lose rights to code they wrote before
            this engagement, which is a significant and non-standard risk."
   elapsed_s: 2.31
```

### Batch 2 (Findings 4–6)

```
🤖 [SemanticVerifier] LLM_CALL
   clause_ref: "Section 6" | category: indemnification

✅ [SemanticVerifier] KEEP
   verdict: YES
   reason: "Indemnification is one-sided — contractor only. Unlimited in
            amount. Covers third-party IP claims, which is particularly
            dangerous given the blanket IP assignment in Section 4."
   elapsed_s: 2.05

🤖 [SemanticVerifier] LLM_CALL
   clause_ref: "Section 7" | category: other_risk

✅ [SemanticVerifier] KEEP
   verdict: YES
   reason: "24-month non-compete for a freelance engagement is extreme.
            Combined with the non-solicitation clause, this could prevent
            the contractor from working in their field for 2 years."
   elapsed_s: 1.87

🤖 [SemanticVerifier] LLM_CALL
   clause_ref: "Missing: Liability cap" | category: liability_cap

✅ [SemanticVerifier] KEEP
   verdict: YES
   reason: "The full contract has no aggregate liability limit anywhere.
            Combined with the unlimited indemnification in Section 6,
            contractor has theoretically unlimited financial exposure."
   elapsed_s: 2.22
```

### Batch 3 (Finding 7)

```
🤖 [SemanticVerifier] LLM_CALL
   clause_ref: "Section 3" | category: payment_terms (worth_raising)
   quote_preview: "Client shall pay Contractor a total fixed fee of $15,000
                   for all services rendered..."

✅ [SemanticVerifier] KEEP
   verdict: YES
   reason: "Lump-sum payment with no milestone schedule on a $15,000
            engagement means contractor does all the work before any
            payment. No progress payments, high non-payment risk."
   elapsed_s: 1.76
```

```
✅ [SemanticVerifier] DECISION
   input: 7 | survived: 7 | dropped: 0
   elapsed_s: 16.33
```

**What shaped the next step:** All 7 findings confirmed by an independent LLM reviewer. Forwarded to synthesis and scoring.

---

## Agent 6 — `ReportSynthesizer` + `BlendedScorer`

**Role:** Compile findings into a structured Markdown report and calculate the final 0–100 safety score.

### ReportSynthesizer

```
▶ [ReportSynthesizer] STEP_START
   action: "Compile verified findings into structured Markdown report"
   input_findings: 7

✅ [ReportSynthesizer] DECISION
   report_chars: 3841
   elapsed_s: 3.12
```

**Report preview:**
```markdown
## Contract Analysis Report

**Safety Score: 23/100** ⚠️ HIGH RISK

### ❗ Critical Issues (must_raise)

**[Section 2] Kill Fee — Client Termination Without Compensation**
> "The Client reserves the right to terminate this Agreement at any time,
> with or without cause, and with or without notice..."

This clause gives the client unconditional right to cancel at any moment
with zero payment obligation. Industry standard requires a kill fee of
25–50% of remaining project value on client-initiated cancellations...
```

### BlendedScorer

```
▶ [BlendedScorer] STEP_START
   formula: "score = 0.6 × rule_score + 0.4 × llm_score"
   alpha: 0.6
   rule_component: "Deterministic regex scanner"
   llm_component: "Weighted severity scoring with diminishing returns"

✅ [BlendedScorer] DECISION
   rule_score: 26
   llm_score: 18
   formula: "60% × 26 + 40% × 18 = 23"
   final_score: 23/100
   stability_band: "±3 points"
   elapsed_s: 0.002
```

**Rule-based deductions applied:**

| Rule | Deduction | Reason |
|---|---|---|
| No kill fee clause | −20 pts | No kill fee protection found anywhere |
| Net-90+ payment terms | −15 pts | Payment > Net-30 standard |
| No aggregate liability cap | −20 pts | Unlimited contractor exposure |
| No late payment penalty | −10 pts | No interest/penalty clause |
| Non-compete > 12 months | −9 pts | Exceeds reasonable scope |

**LLM-based deduction (40% weight):**  
6× `must_raise` findings + 1× `worth_raising` = raw penalty of 82 points → diminishing returns applied (multiple findings per category weighted down) → LLM score of 18.

```
📊 [Pipeline] SUMMARY
   total_elapsed_s: 28.47
   final_safety_score: 23/100
   final_findings: 7
   funnel:
     after_consensus:            7   (1 hallucination filtered)
     after_dedup:                7   (0 duplicates this run)
     after_deterministic_verify: 7   (0 failed grounding)
     after_semantic_verify:      7   (0 failed semantic check)
```

---

## Human Checkpoints

The pipeline has two explicit human-in-the-loop moments, both in the frontend:

| Checkpoint | Trigger | Human Action |
|---|---|---|
| **"Fix It For Me"** | User clicks button on any finding | Reviews the AI-generated safe alternative clause before using it |
| **Document Chat** | User types a question | User formulates a natural-language question; answer is grounded in contract text |

Neither of these modifies the pipeline output. They are post-analysis, user-initiated interactions.

---

## Retry Behaviour

The pipeline has retry logic at two agents. The trajectory above shows a clean run with no retries. A typical retry scenario:

```
🔄 [StructuredAnalyzer] RETRY
   run: 2/3 | attempt: 2/3
   reason: "JSONDecodeError — model returned markdown-fenced JSON instead
            of raw JSON object. Stripped fences and retried."
   delay_s: 2.0   (linear backoff: 2s × attempt_number)
   outcome: RECOVERED — clean JSON on attempt 2
```

```
🔄 [SemanticVerifier] RETRY
   finding: "Section 6 / indemnification" | attempt: 2/3
   reason: "RateLimitError — Groq TPM limit hit during batch processing"
   delay_s: 3.0
   outcome: RECOVERED — verdict returned on attempt 2
```

**Fail-open policy (Semantic Verifier only):** After 3 retries, the finding is *kept* with `verdict: UNCERTAIN`. Rationale: the deterministic verifier has already confirmed the quote exists in the source text; a transient API failure should not destroy a confirmed real finding.

---

## End-to-End Pipeline Timing

| Agent | Action | Runtime |
|---|---|---|
| IngestionPipeline | File parse + SHA-256 | 0.003s |
| ConsensusAnalyzer | 3× concurrent LLM calls | 5.31s |
| FindingsDeduplicator | Overlap check | 0.001s |
| DeterministicVerifier | 4-point grounding | 0.004s |
| SemanticVerifier | 7× batched LLM verdicts | 16.33s |
| ReportSynthesizer | Markdown report | 3.12s |
| BlendedScorer | Rule + LLM blend | 0.002s |
| **Total** | | **28.47s** |

**Cost (OpenAI gpt-4o):** ~$0.13 for this run on `sow_003_risky.txt`.  
**Cache hit cost:** $0.00.

---

*ClauseGuard AI — Agent Trajectories Document — © 2026 Paarth Sharma*
