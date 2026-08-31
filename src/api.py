import os
import tempfile
import asyncio
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
import uvicorn
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware

# Import our ClauseGuard pipeline modules
from .ingestion import IngestionPipeline
from .analyzer import StructuredAnalyzer
from .verifier import DeterministicVerifier
from .semantic_verifier import SemanticVerifier
from .deduplicator import FindingsDeduplicator
from .synthesizer import ReportSynthesizer
from .blended_scorer import BlendedScorer
from .consensus import ConsensusAnalyzer
from .cache import DocumentCache
from .generator import ClauseGenerator
from .chat import ContractChatbot
from .logger import PipelineLogger

app = FastAPI(title="ClauseGuard API")

# Enable CORS so the Next.js frontend (port 3000) can talk to the Python backend (port 8000).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict to your domain!
    allow_methods=["*"],
    allow_headers=["*"],
)

class GenerateAlternativeRequest(BaseModel):
    risky_clause: str
    category: str
    explanation: str

class ChatRequest(BaseModel):
    contract_text: str
    question: str

@app.get("/")
async def root():
    return {"message": "ClauseGuard API is running! Visit /docs to test the API."}


@app.post("/analyze")
async def analyze_contract(file: UploadFile = File(...)):
    """
    Receives a file, runs the full ClauseGuard pipeline, and returns:
      - report: Markdown report
      - findings: structured findings array (cleaned for frontend)
      - score: safety score (0-100)
      - score_breakdown: detailed scoring audit trail
      - contract_text: raw parsed text
      - metrics: pipeline timing metrics
    """
    log = PipelineLogger(file.filename)
    log.step_start("API Request", f"Received file: {file.filename}")

    # 1. Save the uploaded file to temp directory
    suffix = os.path.splitext(file.filename or "")[-1] or ".txt"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await file.read())
        temp_path = tmp.name

    try:
        # 2. Ingestion
        log.step_start("Ingestion", "Parsing document")
        ingestion = IngestionPipeline()
        ingest_result = await asyncio.to_thread(ingestion.process, temp_path)

        if ingest_result["status"] != "SUCCESS":
            raise HTTPException(
                status_code=422,
                detail=f"Ingestion failed: {ingest_result.get('error', 'Unknown error')}"
            )
        parsed_text = ingest_result["parsed_text"]
        log.step_end(details=f"parsed {len(parsed_text)} chars")

        # 2b. Cache check
        cache = DocumentCache()
        log.step_start("Cache Check", "Looking for previous analysis")
        cached = cache.get(parsed_text)
        if cached:
            log.step_end(details="CACHE HIT")
            log.pipeline_summary(cached["score"], len(cached.get("findings", [])))
            # Clean cached findings for frontend
            cached["findings"] = _clean_findings_for_frontend(cached.get("findings", []))
            return cached
        log.step_end(details="CACHE MISS — running full pipeline")

        # 3. Analysis with consensus
        log.step_start("Consensus Analysis", "Running analyzer 3x and voting")
        analyzer = StructuredAnalyzer()
        consensus = ConsensusAnalyzer(num_runs=3, min_consensus=2)
        consensus_result = await consensus.analyze_with_consensus(analyzer, parsed_text)
        raw_findings = consensus_result["findings"]
        meta = consensus_result["consensus_metadata"]
        log.step_end(
            finding_count=len(raw_findings),
            details=f"{meta.get('total_raw_findings', 0)} raw → {meta.get('consensus_findings', 0)} consensus"
        )

        # 4. Deduplication
        log.step_start("Deduplication", "Removing overlapping findings")
        deduped = FindingsDeduplicator().deduplicate(raw_findings)
        log.step_end(finding_count=len(deduped))

        # 5. Deterministic Verification
        log.step_start("Verification", "Schema + Grounding + Confidence checks")
        det_verified = DeterministicVerifier().verify(deduped, parsed_text)
        log.step_end(finding_count=len(det_verified))

        # 6. Semantic Verification
        log.step_start("Semantic Check", "LLM-based legal interpretation")
        sem_verified = await SemanticVerifier().verify_interpretation(det_verified, contract_text=parsed_text)
        log.step_end(finding_count=len(sem_verified))

        # 7. Synthesis
        log.step_start("Synthesis", "Generating markdown report")
        final_report = await ReportSynthesizer().generate_report(sem_verified)
        log.step_end()

        # 8. Blended Scoring (rule-based + LLM-based)
        log.step_start("Blended Score", "Combining rule-based and LLM-based scores")
        blended = BlendedScorer(alpha=0.6)
        score, score_breakdown = blended.calculate_score(sem_verified, parsed_text)
        log.step_end(details=f"score={score}/100")

        # 9. Clean findings for frontend
        clean_findings = _clean_findings_for_frontend(sem_verified)

        log.pipeline_summary(score, len(sem_verified))

        # 10. Cache results
        result_data = {
            "report": final_report,
            "findings": clean_findings,
            "score": score,
            "score_breakdown": score_breakdown,
            "contract_text": parsed_text,
            "metrics": log.get_metrics(),
        }
        cache.set(parsed_text, result_data)

        return result_data

    except HTTPException:
        raise  # Re-raise HTTP exceptions as-is
    except Exception as e:
        log.log_error("Pipeline", e)
        raise HTTPException(
            status_code=500,
            detail=f"Pipeline error: {str(e)}"
        )
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

def _clean_findings_for_frontend(findings: list[dict]) -> list[dict]:  # noqa: E302
    """Strip internal verification fields before sending to frontend."""
    cleaned = []
    for f in findings:
        cleaned.append({
            "clause_ref": f.get("clause_ref", ""),
            "quote": f.get("quote", ""),
            "category": f.get("category", ""),
            "severity": f.get("severity", ""),
            "explanation": f.get("explanation", ""),
            "confidence": f.get("confidence", 0.0),
        })
    return cleaned

@app.post("/generate-alternative")
async def generate_alternative(request: GenerateAlternativeRequest):
    """
    Receives a risky clause and generates a freelancer-friendly alternative.
    """
    print(f"\n--- Generating Alternative for category: {request.category} ---")
    
    generator = ClauseGenerator()
    safe_clause = await generator.generate_alternative(
        request.risky_clause, 
        request.category, 
        request.explanation
    )
    
    return {"safe_clause": safe_clause}

@app.post("/chat")
async def chat_with_contract(request: ChatRequest):
    """
    Answers a question based on the contract context.
    """
    print(f"\n--- Chat Request Received: {request.question} ---")
    
    chatbot = ContractChatbot()
    answer = await chatbot.answer_question(request.contract_text, request.question)
    
    return {"answer": answer}

if __name__ == "__main__":
    # Start the server on port 8000
    print("Starting ClauseGuard API on http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)