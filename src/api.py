import os
import tempfile
from fastapi import FastAPI, UploadFile, File
import uvicorn
from fastapi.middleware.cors import CORSMiddleware

# Import our ClauseGuard pipeline modules
from .ingestion import IngestionPipeline
from .analyzer import StructuredAnalyzer
from .verifier import DeterministicVerifier
from .semantic_verifier import SemanticVerifier
from .synthesizer import ReportSynthesizer

app = FastAPI(title="ClauseGuard API")

# We must enable CORS so our Next.js frontend (running on port 3000) 
# is allowed to talk to our Python backend (running on port 8000).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, restrict this to your domain!
    allow_methods=["*"],
    allow_headers=["*"],
)

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
        ingest_result = IngestionPipeline().process(temp_path)
        
        if ingest_result["status"] != "SUCCESS":
            return {"error": f"Ingestion failed: {ingest_result.get('error')}"}
            
        parsed_text = ingest_result["parsed_text"]
        
        print("Analyzing...")
        raw_findings = StructuredAnalyzer().analyze(parsed_text).get("findings", [])
        
        print("Verifying...")
        det_verified = DeterministicVerifier().verify(raw_findings, parsed_text)
        sem_verified = SemanticVerifier().verify_interpretation(det_verified)
        
        print("Synthesizing Report...")
        final_report = ReportSynthesizer().generate_report(sem_verified)
        
        # Return the final report as JSON to Next.js
        print("Success! Sending report back to frontend.")
        return {"report": final_report}
        
    except Exception as e:
        return {"error": str(e)}
        
    finally:
        # 3. Clean up (delete the temporary file from the server)
        if os.path.exists(temp_path):
            os.remove(temp_path)

if __name__ == "__main__":
    # Start the server on port 8000
    print("Starting ClauseGuard API on http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)