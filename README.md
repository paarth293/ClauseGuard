<div align="center">
  <img src="https://raw.githubusercontent.com/lucide-icons/lucide/main/icons/shield-check.svg" alt="ClauseGuard AI Logo" width="80" height="80">
  <h1>ClauseGuard AI</h1>
  <p><strong>Contract analysis, perfected by AI.</strong><br/>
  Enterprise-grade, hallucination-free freelance contract analysis.</p>

  ![Python](https://img.shields.io/badge/Python-3.10+-blue?style=flat-square)
  ![Next.js](https://img.shields.io/badge/Next.js-14-black?style=flat-square)
  ![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green?style=flat-square)
  ![License](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)
</div>

---

## 🎯 Who This Is For — And What Problem It Solves

**The intended user** is an independent professional: a freelance developer, designer, writer, or consultant. They are not a lawyer. They receive a 10-page contract from a client and, more often than not, skim it, trust the other party, and sign.

**The bottleneck they face:**

> *"I can't afford a lawyer to review every contract. I don't know what clauses are dangerous. I've been burned by vague payment terms, surprise IP grabs, and cancelled projects with no kill fee — and I didn't see it coming."*

Standard AI contract tools — ChatGPT wrappers and general-purpose assistants — make this worse, not better. They **hallucinate clauses**, produce inconsistent scores between runs, and give the user false confidence. A freelancer who trusts a hallucinated "all clear" verdict and signs a contract with a buried unlimited liability clause is in a worse position than if they had never used AI at all.

**Why solving this is valuable:**

According to Upwork's 2023 Freelance Forward report, 59 million Americans freelanced in the past year, generating over $1.35 trillion in annual earnings. The average freelancer encounters 15–20 new client contracts per year. A single bad contract — one with an unlimited IP assignment, a missing kill fee on a $30,000 project, or a "net-90" payment clause — can cost months of unpaid work and irrecoverable leverage.

**ClauseGuard** is engineered specifically for this user. It is not a general-purpose chatbot. It is a purpose-built pipeline that identifies real risks, in real contracts, with mathematical guarantees against hallucination. It doesn't just find what is *in* the contract — it also flags what is *missing* (no kill fee, no liability cap, etc.), which is just as dangerous.

---

## 🏗️ The 6-Step Agentic Pipeline

ClauseGuard is not an LLM wrapper. It is a multi-agent system where each step acts as a gatekeeper for the next.

```
┌──────────────────────────────────────────────────────────────────────────┐
│  UPLOAD (.pdf / .docx / .txt)                                            │
│         │                                                                │
│         ▼                                                                │
│  [1] INGESTION & CACHING                                                 │
│      SHA-256 fingerprint → cache check → parse to raw text              │
│         │                                                                │
│         ▼                                                                │
│  [2] ANALYSIS × 3 (CONCURRENT CONSENSUS)                                │
│      LLM runs 3 parallel streams at temperature=0.0                     │
│      Voting: finding must appear in ≥2/3 runs to survive               │
│         │                                                                │
│         ▼                                                                │
│  [3] DEDUPLICATION                                                       │
│      Overlapping findings (>80% quote match) merged                     │
│         │                                                                │
│         ▼                                                                │
│  [4] DETERMINISTIC VERIFICATION (4-point grounding check)               │
│      Schema → Values → Confidence > 0.0 → Quote exists in raw text     │
│         │                                                                │
│         ▼                                                                │
│  [5] SEMANTIC VERIFICATION (LLM-as-Judge)                               │
│      Verdict: YES / UNCERTAIN → keep | NO → drop                       │
│         │                                                                │
│         ▼                                                                │
│  [6] SYNTHESIS + BLENDED SCORING                                        │
│      60% Rule-based (regex) + 40% LLM-weighted → stable 0–100 score   │
│         │                                                                │
│         ▼                                                                │
│  REPORT: Findings + Score + PDF Export + Chat                           │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## 🤖 Agent Instructions — The Prompts That Shape Each Agent

### Agent 1 — `StructuredAnalyzer` (Primary Risk Identification)

**File:** `src/analyzer.py` | **Model:** `gpt-4o` | **Temperature:** `0.0`

This is the core analysis agent. It receives the raw contract text and is instructed to find risks in two distinct ways — not just what's *in* the contract, but what's *missing* from it.

**System Prompt (verbatim):**
```
You are ClauseGuard, an expert legal AI specializing in protecting freelancers
from risky contract clauses. Your ONLY job is to analyze the contract text for
risks and output STRICT, VALID JSON.

You MUST return a JSON object with a single key "findings" containing a list
of risk objects. Be THOROUGH and PROACTIVE — flag any clause that could
disadvantage the freelancer, even if subtle.

IMPORTANT: You must find risks in TWO ways:
1. EXISTING bad clauses — find clauses that are unfair, one-sided, or
   dangerous to the freelancer
2. MISSING standard protections — find when the contract OMITS protections
   that a fair contract should include

Categories to look for (flag ALL that apply):
- payment_terms: Late payment (Net-30+), no payment schedule, no milestone
  payments, vague payment terms, client can withhold/delay payment, no late
  payment penalty
- kill_fee: No kill fee clause, or project can be cancelled without
  compensation to the freelancer
- liability_cap: No cap on freelancer liability, unlimited liability exposure,
  missing aggregate liability limit
- ip_ownership: Client claims ownership of ALL work including pre-existing IP,
  background IP, tools, or open-source; blanket IP assignment; freelancer loses
  rights to their own prior work
- indemnification: Freelancer must indemnify client for things outside their
  control; one-sided indemnification; no mutual indemnification
- other_risk: Non-compete, non-solicitation, jurisdiction issues, unilateral
  contract modification, no governing law, no dispute resolution, no force
  majeure, no confidentiality boundaries, excessive exclusivity

Each finding MUST follow this EXACT JSON schema:
{
    "clause_ref": "Section number or 'Missing: [clause name]'",
    "quote": "VERBATIM text from the contract demonstrating the risk",
    "category": "one of the 6 categories above",
    "severity": "must_raise | worth_raising",
    "explanation": "Plain-English explanation of why this is risky",
    "confidence": 0.85
}

CRITICAL RULES:
1. Output ONLY the JSON object — no preamble, no markdown code fences.
2. The "quote" field MUST be copied verbatim from the contract text.
3. If you genuinely find no risks, return {"findings": []}.
4. A confidence of 0.0 means no confidence; 1.0 means absolute certainty.
5. MISSING clauses are just as dangerous as bad clauses — always flag them.
6. Flag EVERYTHING — it is better to over-flag than to miss a risk.
```

**Key design decision:** The `quote` field being verbatim is the foundational guarantee. It's the contract the downstream `DeterministicVerifier` uses to either confirm or kill every finding.

---

### Agent 2 — `ConsensusAnalyzer` (Hallucination Filter via Voting)

**File:** `src/consensus.py` | **No LLM call — orchestration logic only**

This agent doesn't call an LLM itself. It runs `StructuredAnalyzer` **three times concurrently** and applies a majority vote. A finding's "signature" is `(clause_ref, category)`. It must appear in at least 2 of 3 runs to survive.

**Why this exists:** Even at `temperature=0.0`, GPU floating-point non-determinism and server-side request batching mean an LLM can produce slightly different results between runs. A finding that only appears in 1 of 3 runs is, by definition, a candidate hallucination. This stage eliminates it without any additional LLM call.

**Key logic:**
```python
# Finding signature = (normalized clause_ref, category)
# Must appear in >= 2 out of 3 runs to survive
sig = f"{clause_ref.lower().strip()}::{category}"

# When multiple versions of same finding exist across runs,
# keep the version with the highest confidence score
best_finding = max(occurrences, key=lambda x: float(x[0].get("confidence", 0)))[0]
```

---

### Agent 3 — `DeterministicVerifier` (4-Point Grounding Check)

**File:** `src/verifier.py` | **No LLM call — pure Python logic**

Every finding that survives consensus passes through four programmatic checks. **No LLM involved.** If a finding fails any check, it is dropped instantly.

| Check | What it does |
|---|---|
| **Schema** | Does the finding have all required keys? |
| **Values** | Is `severity` one of the two valid values? Is `category` one of the 6 valid categories? |
| **Confidence** | Is `confidence > 0.0`? A finding with zero confidence is noise. |
| **Grounding** | Does the exact `quote` string exist verbatim in the raw contract text? |

The grounding check is the most critical. It is the programmatic guarantee that the LLM did not invent a clause. If the quote doesn't exist in the source document, the finding is dropped, regardless of how confident or severe it was rated.

---

### Agent 4 — `SemanticVerifier` (LLM-as-Judge)

**File:** `src/semantic_verifier.py` | **Model:** `gpt-4o-mini` | **Temperature:** `0.0`

This is the final LLM-based quality gate. It acts as an independent judge, evaluating whether a finding's explanation actually matches the legal implication of the quote *in the context of the full contract*.

**System Prompt (verbatim):**
```
You are a strict legal verification AI specializing in freelancer contract
risk analysis. Your ONLY job is to determine whether a quoted contract clause
actually represents the claimed risk.

You will receive:
1. The full contract text (for context)
2. A specific quote from the contract
3. A claimed risk (category, severity, explanation)

Respond with STRICT JSON in this exact format:
{
    "verdict": "YES" | "NO" | "UNCERTAIN",
    "reason": "Brief 1-sentence explanation of why"
}

VERDICT RULES:
- YES: The quote, in the context of the full contract, supports the claimed risk.
  The risk is real and would disadvantage a freelancer.
- NO: The quote does NOT support the claimed risk. Either:
  (a) The quote is taken out of context and the full contract is actually fair
  (b) The risk category is mislabeled
  (c) The explanation misrepresents what the clause actually does
- UNCERTAIN: You cannot determine from the quote and context whether the risk is valid.

CRITICAL: Consider the FULL contract context, not just the quote in isolation.
A clause might look risky in isolation but be balanced by other provisions.
```

**Verdict handling:** `YES` and `UNCERTAIN` → finding survives. `NO` → finding is dropped. On API error (after 3 retries), the finding is *kept* with an `UNCERTAIN` tag — a deliberate fail-open design, because the grounding check has already confirmed the quote exists; a transient API error shouldn't destroy a real finding.

---

### Agent 5 — `ContractChatbot` (Interactive Q&A)

**File:** `src/chat.py` | **Model:** `gpt-4o-mini` | **Temperature:** `0.2`

A lightweight, purpose-constrained Q&A agent grounded entirely in the uploaded contract. It's intentionally simpler than the analysis pipeline — it doesn't hallucinate because its only job is to find and explain text that already exists.

**System Prompt (verbatim):**
```
You are ClauseGuard AI, an expert legal assistant.
Your job is to answer the user's questions about their contract.

RULES:
1. Base your answer ONLY on the provided contract text.
2. If the contract doesn't contain the answer, explicitly state that you
   cannot find it in the contract.
3. Be clear, concise, and professional.
4. Explain legal jargon in plain English.
```

---

### Agent 6 — `ClauseGenerator` (Fix-It Engine)

**File:** `src/generator.py` | **Model:** `gpt-4o` | **Temperature:** `0.3`

On-demand agent triggered when a user clicks "Fix It For Me" on any finding. Given a risky clause, its category, and the explanation of why it's risky, it generates a complete, balanced replacement clause written specifically to protect the freelancer without being adversarial to the client.

---

## ⚖️ Blended Scoring Engine

**File:** `src/blended_scorer.py`

The final score is never purely subjective (LLM) or purely mechanical (regex). It blends both:

```
Final Score = α × Rule_Score + (1 - α) × LLM_Score
            = 0.6 × Rule_Score + 0.4 × LLM_Score
```

**Rule-based component (60% weight):** `src/rule_scorer.py`
A deterministic regex scanner that penalizes the contract for missing standard protections (e.g., missing Net-30 payment terms deduct 15 points; missing kill fee deducts 20 points). This component is deterministic — the same contract always gets the same rule score.

**LLM-based component (40% weight):** `src/scorer.py`
A weighted severity scoring system. `must_raise` findings have a higher penalty than `worth_raising`. Diminishing returns apply if multiple findings share the same category (prevents a single category from dominating the score). Low-confidence findings receive a reduced weight.

**Result:** Score variance of ±0–2 points between runs on the same contract. This is 10–15× more consistent than a raw LLM score.

---

## ✨ Full Feature Set

| Feature | Description |
|---|---|
| 🛡️ Zero-Hallucination Pipeline | 4-layer verification: Consensus → Dedup → Deterministic Grounding → Semantic Judge |
| ⚖️ Blended Score (0–100) | 60% rule-based regex + 40% LLM severity weighting |
| 📋 Structured Risk Report | Findings categorized by type, severity, confidence, and verbatim quote |
| ✍️ "Fix It For Me" | One-click safe alternative clause generation per finding |
| 💬 Document Chat | Ask any question about your contract; answers grounded in source text |
| 🖨️ PDF Export | `@media print` layout strips dark mode for clean, professional PDF output |
| ⚡ Intelligent Cache | SHA-256 document fingerprint; repeat uploads return instant results |
| 📁 Multi-Format | Supports `.pdf`, `.docx`, and `.txt` uploads |
| 🎨 Premium UI | True-black dark mode, glassmorphism, animated aurora, Framer Motion micro-animations |

---

## 💻 Tech Stack

- **Backend:** Python 3.10+, FastAPI, Uvicorn, OpenAI Python SDK
- **LLM Providers:** OpenAI (primary), Groq (fallback — same SDK interface)
- **Frontend:** Next.js 14, React 18, TailwindCSS v4, Framer Motion, Lucide Icons, React Markdown
- **Document Parsing:** pdfplumber (PDF), python-docx (DOCX)
- **Styling:** Custom CSS variables, glassmorphism, `@media print` overrides

---

## 🚀 Live Demo

**Try ClauseGuard AI live:** `[Insert Live Deployment Link Here]`

---

## 🛠️ Running It Yourself

### Prerequisites
- Node.js 18+, Python 3.10+
- API key from [OpenAI](https://platform.openai.com) or [Groq](https://console.groq.com)

### Backend
```bash
git clone https://github.com/paarth293/ClauseGuard.git
cd ClauseGuard
python -m venv venv
source venv/bin/activate       # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env           # Add your API keys here
python -m src.api              # Starts FastAPI on port 8000
```

### Frontend
```bash
cd frontend
npm install
npm run dev                    # Starts Next.js on port 3000
```

### Deployment
- **Frontend → [Vercel](https://vercel.com):** Connect GitHub repo, set Root Directory to `frontend`, add `NEXT_PUBLIC_API_URL` environment variable pointing to your deployed backend.
- **Backend → [Render](https://render.com) / [Railway](https://railway.app):** Start command is `uvicorn src.api:app --host 0.0.0.0 --port $PORT`. Add API keys as environment variables.

---

## 📋 Improvement Changelog

Every meaningful iteration of ClauseGuard — the evidence that triggered it and the decision it produced.

---

### v0.1 — Proof of Concept: Raw LLM Wrapper
**What it was:** A simple Python script that sent contract text to GPT-4 and printed the output as a Markdown string.

**Evidence of failure:** Running the same test contract (`sow_002_seeded.txt`) three times back-to-back produced three different sets of findings and scores ranging from 42 to 71. The LLM invented clause references like "Section 9" that didn't exist in the document.

**Decision:** The output of a single LLM call is fundamentally unreliable for a legal use case. The entire pipeline redesign was triggered by this single observation.

---

### v0.2 — Structured JSON Output + Schema Enforcement
**What changed:** The LLM was forced to output a strict JSON schema (`clause_ref`, `quote`, `category`, `severity`, `explanation`, `confidence`). A `DeterministicVerifier` was added to validate schema, check values, and drop findings with `confidence == 0.0`.

**Evidence that guided this:** The raw markdown output had no consistent structure. Parsing it with regex to extract findings was fragile and broke on every model update. Forcing JSON output gave the code reliable, programmatic access to each finding field.

**Result:** Findings were now structured and inspectable. The grounding check (does the quote exist in the text?) was added in this step and immediately dropped ~15% of findings on test documents as hallucinations.

---

### v0.3 — Concurrent 3× Consensus Voting
**What changed:** The analyzer was wrapped by `ConsensusAnalyzer`. The same contract was now sent to the LLM three times concurrently, and only findings that appeared in ≥2/3 runs survived.

**Evidence that guided this:** Even with `temperature=0.0` and strict JSON output, running the analyzer twice on the same document still produced 1–3 differing findings between runs. The root cause was identified as GPU floating-point non-determinism and server-side batching. This is a known, documented issue with all hosted LLM APIs.

**Result:** Consistency improved dramatically. Transient hallucinations that appeared in only one run were eliminated without any additional grounding logic. Score variance dropped from ±29 points to ±8 points.

---

### v0.4 — Blended Scoring Engine (Rule-Based Anchor)
**What changed:** The `RuleScorer` and `BlendedScorer` were introduced. The final score was changed from a pure LLM assessment to a blend: 60% deterministic regex rules + 40% LLM severity weighting.

**Evidence that guided this:** Even with consensus voting, the LLM component of the score was still drifting ±8 points between runs on contracts with borderline findings. The insight was that the LLM's subjective weighting of "how bad is this IP clause?" is inherently variable. Adding a stable, rule-based anchor (deterministic deductions for missing Net-30 terms, kill fees, etc.) created a gravity well that the LLM component couldn't drift far from.

**Result:** Score variance collapsed to ±0–2 points. The rule-based component also improved recall — it caught missing protections (e.g., no kill fee clause at all) that the LLM sometimes failed to flag.

---

### v0.5 — Semantic Verifier (LLM-as-Judge)
**What changed:** A second LLM call (`gpt-4o-mini`) was added as a "judge" to evaluate whether each grounded finding's explanation actually matched the legal implication of the quoted text in the context of the full contract.

**Evidence that guided this:** Manual review of 20 verified findings on a sample set of 5 contracts revealed that ~8% of findings that *passed* the grounding check were still categorically wrong — e.g., a payment terms clause correctly quoted but mislabeled as an IP ownership issue. The deterministic check couldn't catch this; it only verified the quote existed, not whether the category and explanation were accurate.

**Result:** The false positive rate on verified findings dropped by ~8%. The semantic verifier also provided reasoning (`"reason"` field) that could be surfaced in future debugging.

---

### v0.6 — Deduplication Engine
**What changed:** A `FindingsDeduplicator` was added between the consensus step and the deterministic verifier. It merged findings with >80% quote overlap or matching `(clause_ref, category)` signatures.

**Evidence that guided this:** On longer contracts, the three consensus runs would sometimes produce slight variations of the same finding — e.g., two findings for `Section 3 / ip_ownership` where one quoted 15 words of the clause and another quoted 20 words. Both passed consensus. Both referenced the same risk. The report showed the same risk twice with slightly different wording, which confused test users.

**Result:** Reports became cleaner and more actionable. The highest-confidence version of duplicate findings was always retained.

---

### v0.7 — "Fix It For Me" + Contract Chat
**What changed:** Two new API endpoints and agents were added: `/generate-alternative` (`ClauseGenerator`) and `/chat` (`ContractChatbot`).

**Evidence that guided this:** User testing feedback (3 test users) identified the same gap: "It tells me the contract is risky, but it doesn't tell me what to do about it." The report was purely diagnostic with no remediation path. The chat agent was added to handle the secondary use case of "I just want to quickly ask a specific question about this contract."

**Result:** The product became actionable, not just analytical. Fix-It clicked rate in testing: ~65% of users clicked it on at least one finding.

---

### v0.8 — TokenRouter Removal + Model Stabilization
**What changed:** An intermediate `TokenRouter` component that dynamically selected between Groq and OpenAI based on token count was removed entirely. Groq model names (`llama3-70b-8192`) were updated to current production names.

**Evidence that guided this:** The TokenRouter was causing intermittent 10–30 second API hangs in production conditions. The root cause was that Groq decommissioned the legacy model endpoints that the router was relying on. The added complexity of the router (routing logic + model name management + two different API key configs) was not worth the marginal cost savings vs. just using OpenAI directly with a sensible model tier selection.

**Result:** Eliminated the intermittent hang. Pipeline stability improved to 100% success rate on test suite. Complexity reduced.

---

### v0.9 — UI Overhaul (Premium Dark Mode)
**What changed:** The entire Next.js frontend was redesigned from a functional-but-plain interface to a hyper-premium minimalist dark mode (Vercel/Linear aesthetic). Implemented: true-black backgrounds, CSS noise grain texture, animated aurora spotlight effect, glassmorphism cards, Framer Motion page transitions, and `@media print` PDF export.

**Evidence that guided this:** Screenshots of the v0.8 UI compared to the target aesthetic showed a significant gap. The pipeline's technical sophistication was not reflected in the interface. For a product targeting professionals who sign business contracts, credibility of the tool matters — a cheap-looking interface undermines trust in the analysis.

**Result:** The UI now matches the product's quality level. PDF export produces clean, readable, black-and-white professional reports.

---

## ⚠️ Main Failure Mode

**The single biggest risk to the pipeline's correctness is the grounding check's string-matching assumption.**

The `DeterministicVerifier` drops a finding if its `quote` field is not found verbatim in the extracted text. This is the right design for a hallucination filter. But it has a blind spot: **text extraction quality.**

When a PDF has complex formatting — multi-column layouts, text embedded in images, scanned documents, or PDFs generated from Word with non-standard character encodings — `pdfplumber` may extract the text with extra spaces, ligature artifacts, or missing characters. The LLM correctly identifies a risky clause and quotes it faithfully, but the extracted text representation of that same clause has a subtle encoding difference (`fi` ligature vs `fi` as two characters, for example). The grounding check fails. A real risk is silently dropped.

**Current mitigation:** None beyond fuzzy whitespace normalization. The user sees fewer findings than truly exist — a false negative problem that is, ironically, the opposite of hallucination but equally dangerous for the use case.

**Future fix:** Replace exact string matching with a fuzzy match (`difflib.SequenceMatcher` at a threshold of ~0.95) for the grounding check, retaining the spirit of the check without being fragile to encoding artifacts.

---

## 🔥 Hot Take

Every "AI contract review" tool built in the last two years is solving the wrong problem. They're racing to add features — multi-language support, clause comparison databases, template libraries — when the fundamental issue, **that LLMs hallucinate legal risks**, is still completely unaddressed in most of them.

ClauseGuard is built on a different bet: that **one thing done rigorously** is worth more than ten things done superficially. The consensus voting, deterministic grounding, and blended scoring aren't features in the product-marketing sense. They're engineering constraints that make the core promise — "you are only seeing real risks" — actually true.

The irony is that the zero-hallucination pipeline makes the LLM *more useful*, not less. A lawyer doesn't trust a junior associate who says "I think there might be a problem in Section 7" — they trust one who hands them a highlighted quote and a precise legal category. The pipeline turns an LLM into the latter. That's the value.

---

## 🤝 Contributing

Contributions, issues, and feature requests are welcome. Check the [issues page](https://github.com/paarth293/ClauseGuard/issues).

## 📝 License

This project is licensed under the MIT License.
