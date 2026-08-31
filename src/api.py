import os
import tempfile
import asyncio
from fastapi import FastAPI, UploadFile, File
import uvicorn
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware

# Import our ClauseGuard pipeline modules
from .ingestion import IngestionPipeline
from .analyzer import StructuredAnalyzer
from .verifier import DeterministicVerifier
from .semantic_verifier import SemanticVerifier
from .synthesizer import ReportSynthesizer
from .scorer import RiskScorer
from .generator import ClauseGenerator
from .chat import ContractChatbot

app = FastAPI(title="ClauseGuard API")

# We must enable CORS so our Next.js frontend (running on port 3000) 
# is allowed to talk to our Python backend (running on port 8000).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, restrict this to your domain!
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
    Receives a file from the Next.js frontend, runs it through ClauseGuard, 
    and returns the final Markdown report.
    """
    print(f"\n--- API Request Received: {file.filename} ---")
    
    # 1. Save the uploaded file to the OS temp directory (always writable)
    suffix = os.path.splitext(file.filename)[-1]  # preserve .pdf/.docx/.txt
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await file.read())
        temp_path = tmp.name
        
    try:
        # 2. Run the file through the exact pipeline we built
        print("Ingesting...")
        # Run synchronous ingestion in a thread pool so it doesn't block FastAPI
        ingestion = IngestionPipeline()
        ingest_result = await asyncio.to_thread(ingestion.process, temp_path)
        
        if ingest_result["status"] != "SUCCESS":
            return {"error": f"Ingestion failed: {ingest_result.get('error')}"}
            
        parsed_text = ingest_result["parsed_text"]
        
        print("Analyzing...")
        analyzer_result = await StructuredAnalyzer().analyze(parsed_text)
        raw_findings = analyzer_result.get("findings", [])
        
        print("Verifying...")
        det_verified = DeterministicVerifier().verify(raw_findings, parsed_text)
        sem_verified = await SemanticVerifier().verify_interpretation(det_verified)
        
        print("Synthesizing Report...")
        final_report = await ReportSynthesizer().generate_report(sem_verified)
        
        print("Calculating Risk Score...")
        score = RiskScorer().calculate_score(sem_verified)
        
        # Return the final report and the structured findings as JSON to Next.js
        print("Success! Sending report back to frontend.")
        return {
            "report": final_report,
            "findings": sem_verified,
            "score": score,
            "contract_text": parsed_text
        }
        
    except Exception as e:
        return {"error": str(e)}
        
    finally:
        # 3. Clean up (delete the temporary file from the server)
        if os.path.exists(temp_path):
            os.remove(temp_path)

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