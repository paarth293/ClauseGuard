# ClauseGuard AI — Reproduction Guide

> **Audience:** A technical reviewer starting from a clean machine with no prior context.  
> **Goal:** Reproduce every result end-to-end — solution pipeline, baseline, and evaluation — with exact commands, expected outputs, runtime, and cost.

---

## Table of Contents

1. [Prerequisites & Versions](#1-prerequisites--versions)
2. [Environment Setup](#2-environment-setup)
3. [Data Required](#3-data-required)
4. [Running the Baseline](#4-running-the-baseline)
5. [Running the Full Solution Pipeline](#5-running-the-full-solution-pipeline)
6. [Running the Evaluation Protocol](#6-running-the-evaluation-protocol)
7. [Running the API Server](#7-running-the-api-server)
8. [Running the Frontend](#8-running-the-frontend)
9. [Expected Outputs](#9-expected-outputs)
10. [Runtime & Cost Reference](#10-runtime--cost-reference)
11. [Troubleshooting](#11-troubleshooting)

---

## 1. Prerequisites & Versions

The following software must be installed on your machine before proceeding.

| Dependency | Version Tested | Install |
|---|---|---|
| **Python** | `3.10.x` – `3.12.x` | [python.org](https://www.python.org/downloads/) |
| **Node.js** | `18.x` or `20.x` | [nodejs.org](https://nodejs.org/) |
| **npm** | `9.x` or `10.x` | Bundled with Node.js |
| **git** | Any recent version | [git-scm.com](https://git-scm.com/) |
| **OpenAI API Key** | — | [platform.openai.com/api-keys](https://platform.openai.com/api-keys) |
| **Groq API Key** *(optional fallback)* | — | [console.groq.com/keys](https://console.groq.com/keys) |

> **Note on API keys:** You need **at least one** of the two. OpenAI is the primary provider (higher quality). Groq is a fast, lower-cost fallback. The pipeline auto-detects which key is present.

### Python Library Versions (from `requirements.txt`)

```
fastapi
uvicorn[standard]
python-multipart
python-dotenv
groq
openai
pdfplumber
python-docx
```

---

## 2. Environment Setup

### Step 1 — Clone the repository

```bash
git clone https://github.com/paarth293/ClauseGuard.git
cd ClauseGuard
```

### Step 2 — Create and activate a Python virtual environment

**macOS / Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

**Windows (PowerShell):**
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

**Windows (Command Prompt):**
```cmd
python -m venv venv
venv\Scripts\activate.bat
```

You should see `(venv)` prepended to your shell prompt. All subsequent `pip` and `python` commands must be run inside this environment.

### Step 3 — Install Python dependencies

```bash
pip install -r requirements.txt
```

Expected output (abbreviated):
```
Collecting fastapi
  Downloading fastapi-0.115.x-py3-none-any.whl
...
Successfully installed fastapi-0.115.x uvicorn-0.30.x pdfplumber-0.11.x ...
```

### Step 4 — Configure environment variables

```bash
cp .env.example .env
```

Open `.env` and fill in your key(s):

```dotenv
# .env — use OpenAI OR Groq (at least one required)
# If OPENAI_API_KEY is present, it takes priority.

OPENAI_API_KEY=sk-proj-xxxxxxxxxxxxxxxxxxxxxxxxxxxx

# Optional: Groq fallback (used only if OPENAI_API_KEY is absent)
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

### Step 5 — Verify configuration

```bash
python -m src.llm
```

Expected output (OpenAI):
```
Active provider: openai
  analysis:     gpt-4o
  verification: gpt-4o
  synthesis:    gpt-4o
  generation:   gpt-4o-mini
  chat:         gpt-4o-mini

Client base_url: https://api.openai.com/v1/
```

Expected output (Groq only):
```
Active provider: groq
  analysis:     openai/gpt-oss-120b
  verification: openai/gpt-oss-120b
  synthesis:    openai/gpt-oss-120b
  generation:   openai/gpt-oss-20b
  chat:         openai/gpt-oss-20b

Client base_url: https://api.groq.com/openai/v1/
```

If you see `RuntimeError: Neither OPENAI_API_KEY nor GROQ_API_KEY found`, your `.env` file is not configured or not in the project root.

---

## 3. Data Required

All required data is **included in the repository**. No external downloads needed.

### Test Contracts (`contracts/`)

| File | Description | Seeded Risks |
|---|---|---|
| `sow_001_clean.txt` | Minimal benign Statement of Work. Negative control. | None |
| `sow_002_seeded.txt` | Short contract with **1 deliberately embedded risk**: blanket IP assignment including pre-existing background IP (Section 3). | 1 × `ip_ownership` |
| `sow_003_risky.txt` | Full 10-section Independent Contractor Agreement with **7 intentional risks** across all major risk categories. Primary evaluation contract. | `kill_fee`, `payment_terms` ×2, `ip_ownership`, `indemnification`, `other_risk`, `liability_cap` |

### Ground Truth (`data/tracker.csv`)

The evaluation protocol reads its answer key from `data/tracker.csv`. Schema:

```
contract_id,clause_ref,risk_type,severity,description
```

Contains **8 total ground-truth risks** across the two seeded contracts.

### Your Own Contracts

You can run the pipeline against any `.pdf`, `.docx`, or `.txt` file. The only requirement is that the file contains parseable text (not a scanned image). Drop the file in the `contracts/` directory or reference it by absolute path when calling the API.

---

## 4. Running the Baseline

The **baseline** represents how most people naively use AI for contracts: a single, unstructured free-text prompt with no schema, no verification, and no retry logic. It uses `openai/gpt-oss-20b` via Groq (requires `GROQ_API_KEY`).

> **Purpose:** Establish the floor — the raw quality of an unconstrained LLM — before any pipeline enhancements are applied.

### Command

```bash
python -m src.baseline
```

### What it does

1. Loads `contracts/sow_002_seeded.txt`.
2. Sends the full text to the LLM with a single unstructured prompt:  
   *"List any risks or issues the freelancer should be aware of."*
3. Prints the raw free-text response.

### Expected output (approximate)

```
1. Ingesting the 'Seeded' contract...
2. Running Baseline Analysis (This might take a few seconds)...

==================================================
BASELINE ANALYSIS RESULT:
==================================================
Here are the key risks and issues in this contract for the freelancer:

**Intellectual Property Ownership (Section 3)**
The contract states that "all work product, including all prior inventions,
pre-existing background IP, and open-source tools used in this project, shall
become the exclusive property of the Client." This is an extremely broad IP
assignment clause...

[...continues as free-form unstructured text...]
```

### Baseline limitations (what the full pipeline improves)

- **No structured output.** Wall of prose — not actionable in code.
- **No grounding.** The LLM may reference sections that do not exist.
- **No consistency.** Two runs produce different wording, structure, and findings.
- **No severity scoring.** No 0–100 score, no `must_raise` vs `worth_raising`.

**Runtime:** ~3–5 seconds. **Cost:** ~$0.001.

---

## 5. Running the Full Solution Pipeline

You can run each agent module independently for debugging, or trigger the full pipeline via the API (Section 7). Each module below uses `contracts/sow_002_seeded.txt` as its default test input.

### 5a — Ingestion

```bash
python -m src.ingestion
```

Expected output:
```
Status: SUCCESS
File Hash: a7f3c2d1e8b9...
Extracted Text (first 100 chars): STATEMENT OF WORK

Section 1. Services
The Freelancer agrees to provide ...
```

### 5b — Analyzer (Single LLM Call, No Verification)

```bash
python -m src.analyzer
```

Expected output (abbreviated):
```
1. Ingesting the 'Seeded' contract...
2. Running Structured Analysis (Strict JSON)...

==================================================
STRUCTURED FINDINGS:
==================================================
{
    "findings": [
        {
            "clause_ref": "Section 3",
            "quote": "all work product, including all prior inventions...",
            "category": "ip_ownership",
            "severity": "must_raise",
            "explanation": "This clause assigns the freelancer's pre-existing IP...",
            "confidence": 0.95
        }
    ]
}

Total Risks Found: 1
```

### 5c — Deterministic Verifier

Runs ingestion → analysis → 4-point grounding check.

```bash
python -m src.verifier
```

Expected output (abbreviated):
```
Original AI findings: 1
Verified findings that survived: 1

"verification_checks": {
    "schema_valid": "PASS",
    "values_valid": "PASS",
    "grounding": "PASS",
    "confidence": "PASS"
}
```

If a finding fails grounding, you will see:
```
"grounding": "FAIL (quote not found; overlap=42%)"
```
That finding is silently dropped — zero tolerance.

### 5d — Semantic Verifier (LLM-as-Judge)

```bash
python -m src.semantic_verifier
```

Expected output:
```
Sending 1 finding(s) to Semantic Verifier...

"semantic_check": {
    "verdict": "YES",
    "reason": "The clause explicitly transfers pre-existing background IP..."
}
```

Verdicts: `YES` or `UNCERTAIN` → finding survives. `NO` → finding is dropped.

### 5e — Blended Scorer

Tests the scoring engine in isolation with mock data (no LLM call required).

```bash
python -m src.blended_scorer
```

Expected output:
```
Blended Score: 42/100
  LLM score:   35
  Rule score:  46
  Formula:     60% × 46 + 40% × 35 = 42
  Stability:   ±4 points

Rule breakdown:
  - No Net-30 payment terms: -15
  - No kill fee clause: -20

Blended score determinism: [42, 42, 42, 42, 42]
Variance: 0 points
```

The final line proves the rule-based anchor eliminates all score drift.

### 5f — Consensus Voting (No LLM, Mock Data)

```bash
python -m src.consensus
```

Expected output:
```
Total raw findings across 3 runs: 5
Consensus findings: 2
Dropped (hallucinations): 3

  + [ip_ownership] section 3 (conf=0.9, runs=2/2)
  + [payment_terms] section 2 (conf=0.8, runs=2/2)
```

The `other_risk` hallucination (appeared in only 1 of 3 runs) is correctly dropped.

---

## 6. Running the Evaluation Protocol

Measures **precision** (hallucination rate) and **recall** (miss rate) against the labelled ground truth.

### Command

```bash
python -m src.evaluate
```

### What it does

1. Reads `data/tracker.csv` to get the ground-truth risk list.
2. For each contract in the CSV, runs: Ingestion → Analyzer → Deduplication → Deterministic Verifier → Semantic Verifier.
3. Compares found `category` values against expected `risk_type`.
4. Calculates True Positives, False Negatives, and False Positives.
5. Prints Recall and Precision.

### Expected Output

```
Starting ClauseGuard Evaluation Protocol...

Evaluating sow_002_seeded.txt...

Evaluating sow_003_risky.txt...

==================================================
 FINAL EVALUATION METRICS
==================================================
Total True Positives (Caught Risks):   7
Total False Negatives (Missed Risks):  1
Total False Positives (Hallucinations): 0
--------------------------------------------------
RECALL:    87.5% (Core promise: Not missing things)
PRECISION: 100.0% (Core promise: Not inventing things)
==================================================
```

**Interpreting results:**

| Metric | Value | What it means |
|---|---|---|
| **Precision = 100%** | 0 hallucinations survived all 4 verification layers | Every reported risk is real and verifiable in the source text |
| **Recall = ~87.5%** | 1 of 8 risks occasionally missed | The `liability_cap` "missing clause" finding is the hardest — the LLM must flag an *absence* rather than a present clause; it succeeds ~60–70% of runs |

**Runtime:** ~60–120 seconds (2 contracts through full pipeline).  
**Cost (OpenAI):** ~$0.08–$0.15 total.

---

## 7. Running the API Server

The FastAPI backend runs all agents and exposes the pipeline over HTTP.

### Command

```bash
python -m src.api
```

Expected output:
```
INFO:     Started server process [12345]
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

### Endpoints

| Method | Endpoint | Input | Description |
|---|---|---|---|
| `GET` | `/` | — | Health check |
| `POST` | `/analyze` | `multipart/form-data`, field `file` | Full 6-step pipeline |
| `POST` | `/generate-alternative` | `{risky_clause, category, explanation}` | Fix-It engine |
| `POST` | `/chat` | `{contract_text, question}` | Document Q&A |

### Test via curl

```bash
curl -X POST http://localhost:8000/analyze \
  -F "file=@contracts/sow_003_risky.txt"
```

Or visit `http://localhost:8000/docs` for interactive Swagger UI.

### `/analyze` Response Schema

```json
{
  "report": "## Contract Analysis Report\n...",
  "findings": [
    {
      "clause_ref": "Section 3",
      "quote": "Payment shall be made within ninety (90) days...",
      "category": "payment_terms",
      "severity": "must_raise",
      "explanation": "Net-90 payment terms give the client 3 months...",
      "confidence": 0.95
    }
  ],
  "score": 23,
  "score_breakdown": {
    "blended_score": 23,
    "llm_score": 18,
    "rule_score": 26,
    "alpha": 0.6,
    "blending_formula": "60% × 26 + 40% × 18 = 23",
    "stability_band": "±3 points"
  },
  "contract_text": "INDEPENDENT CONTRACTOR AGREEMENT...",
  "metrics": {}
}
```

---

## 8. Running the Frontend

### Install dependencies

```bash
cd frontend
npm install
```

### Start development server

```bash
npm run dev
```

Expected output:
```
  ▲ Next.js 14.x.x
  - Local: http://localhost:3000

 ✓ Ready in 1.2s
```

Open `http://localhost:3000`. The API server (`python -m src.api`) must be running simultaneously in a separate terminal.

---

## 9. Expected Outputs Summary

| Contract | Findings (approx.) | Score |
|---|---|---|
| `sow_001_clean.txt` | 0 | 92–98 / 100 |
| `sow_002_seeded.txt` | 1 (`ip_ownership`) | 55–65 / 100 |
| `sow_003_risky.txt` | 5–7 (all major categories) | 18–28 / 100 |

**Score variance between runs on the same document: ±0–2 points.** This is the direct result of the 60% rule-based scoring anchor.

---

## 10. Runtime & Cost Reference

Runtimes measured on a consumer laptop with standard API latency (~1–2s per call). Groq is generally 2–3× faster.

### Per-Component

| Component | Approx. Runtime |
|---|---|
| Ingestion (any format) | < 0.5s |
| Analyzer ×1 LLM call | 3–6s |
| Consensus (3× concurrent) | 4–8s total |
| Deduplication | < 0.1s |
| Deterministic Verifier | < 0.1s |
| Semantic Verifier (per finding) | 2–4s |
| Blended Scoring | < 0.1s |

### Full Pipeline End-to-End

| Contract Size | Findings | Total Runtime |
|---|---|---|
| Short (~500 chars) | 1–2 | 15–25s |
| Medium (~2,000 chars) | 5–8 | 30–60s |
| Long (~10,000 chars) | 6–12 | 60–120s |

### Cost Per Analysis

**OpenAI (GPT-4o):**

| Component | Model | Approx. Cost |
|---|---|---|
| Consensus (3× Analyzer) | `gpt-4o` | ~$0.045 |
| Semantic Verifier (×6 findings avg) | `gpt-4o` | ~$0.055 |
| Synthesis | `gpt-4o` | ~$0.012 |
| **Total per analysis** | | **~$0.11–$0.15** |

**Groq fallback:** ~$0.008–$0.015 per analysis (10–15× cheaper).

**Cache hit:** If the same document has been analyzed before (SHA-256 match), the entire LLM pipeline is bypassed. **Cost: $0.00.**

---

## 11. Troubleshooting

**`RuntimeError: Neither OPENAI_API_KEY nor GROQ_API_KEY found`**  
Your `.env` file is missing, in the wrong directory, or the key is misspelled. Ensure the file is at the project root (same level as `requirements.txt`).

**`ModuleNotFoundError: No module named 'src'`**  
Run all `python -m src.xxx` commands from the **project root** — not from inside the `src/` folder.

**`pdfplumber` fails / extracts empty text**  
The PDF is likely scanned (image-only). Convert to `.txt` first. OCR support is a known limitation.

**Vercel: `No project table found in pyproject.toml`**  
Ensure `pyproject.toml` uses the PEP 621 `[project]` table format, not `[tool.poetry]`. Vercel's `uv` build tool only understands PEP 621.

**Vercel: `FUNCTION_INVOCATION_FAILED` (500)**  
Check the Vercel function logs for a Python traceback. Most common causes:
1. Missing `OPENAI_API_KEY` — add in Vercel → Settings → Environment Variables.
2. Missing dependencies — check all packages are under `[project].dependencies` in `pyproject.toml`.

**Frontend: `Failed to fetch` or CORS error**  
The API server is not running, or the `NEXT_PUBLIC_API_URL` points to the wrong address.

---

*ClauseGuard AI — © 2026 Paarth Sharma. MIT License.*
