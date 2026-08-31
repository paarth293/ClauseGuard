import json
from dotenv import load_dotenv
from groq import AsyncGroq

load_dotenv()

class ReportSynthesizer:
    def __init__(self):
        self.client = AsyncGroq()
        self.model = "openai/gpt-oss-120b"

    async def generate_report(self, verified_findings: list) -> str:
        """
        Generates a professional markdown report.
        Combines a deterministic header/disclaimer with an LLM-synthesized summary.
        """
        
        # 1. Deterministic Header (Honest Uncertainty)
        header = self._generate_header(len(verified_findings))
        
        # 2. LLM Synthesis (Drafting the explanations clearly)
        # If there are no findings, we skip the LLM call entirely to save money and time!
        if not verified_findings:
            return header + "\n\n✅ **Review Complete: No critical risks identified in the covered categories.**"

        findings_json = json.dumps(verified_findings, indent=2)
        
        system_prompt = """
        You are a professional legal assistant. Your job is to format the provided JSON risks into a clean, readable Markdown report for a freelancer to review.
        
        RULES:
        1. Use the heading "### Items to Raise"
        2. For each risk, create a bold bullet point with the Category and Clause Reference.
        3. Provide the exact quote in a blockquote (>).
        4. Provide the explanation clearly.
        5. NEVER invent new risks. ONLY use the provided JSON.
        6. Do NOT give definitive legal advice (e.g. say "Consider discussing this" instead of "You must remove this").
        """
        
        try:
            response = await self.client.chat.completions.create(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Here are the verified findings to format:\n\n{findings_json}"}
                ],
                model=self.model,
                temperature=0.2,
            )
            synthesis = response.choices[0].message.content
        except Exception as e:
            synthesis = f"Error generating synthesis: {str(e)}"
        
        # 3. Deterministic Disclaimer (Must be prominent at the bottom)
        disclaimer = "\n\n---\n*⚠️ DISCLAIMER: ClauseGuard is an AI tool, not a lawyer. This report is for informational purposes to help you prepare for negotiations. It does not constitute legal advice.*"
        
        return header + "\n\n" + synthesis + disclaimer

    def _generate_header(self, finding_count: int) -> str:
        status = "⚠️ ISSUES FOUND" if finding_count > 0 else "✅ CLEAN"
        return f"""╔══════════════════════════════════════════════════════╗
║  CLAUSEGUARD REVIEW                                  ║
║  Status: {status:<43} ║
║  Verified Findings: {finding_count:<33} ║
╚══════════════════════════════════════════════════════╝"""


# --- Testing Code ---
if __name__ == "__main__":
    import os
    import asyncio
    from .ingestion import IngestionPipeline
    from .analyzer import StructuredAnalyzer
    from .verifier import DeterministicVerifier
    from .semantic_verifier import SemanticVerifier
    
    async def run_test():
        print("Running the COMPLETE ClauseGuard Pipeline...\n")
        
        test_path = os.path.join(os.path.dirname(__file__), "../contracts/sow_002_seeded.txt")
        
        # 1. Ingest
        parsed_text = IngestionPipeline().process(test_path)["parsed_text"]
        
        # 2. Analyze
        findings = await StructuredAnalyzer().analyze(parsed_text)
        findings = findings.get("findings", [])
        
        # 3. Verify
        det_verified = DeterministicVerifier().verify(findings, parsed_text)
        sem_verified = await SemanticVerifier().verify_interpretation(det_verified)
        
        # 4. Synthesize
        report = await ReportSynthesizer().generate_report(sem_verified)
        
        print(report)
        
    asyncio.run(run_test())