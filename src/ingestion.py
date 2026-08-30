import hashlib
import os
import pdfplumber
import docx

class IngestionPipeline:
    def process(self, file_path: str) -> dict:
        result = {
            "file_hash": None,
            "parsed_text": None,
            "status": "FAILED",
            "error": None
        }

        try:
            with open(file_path, 'rb') as f:
                file_bytes = f.read()
                result["file_hash"] = hashlib.sha256(file_bytes).hexdigest()
            
            _, ext = os.path.splitext(file_path.lower())
            
            if ext == '.txt':
                result["parsed_text"] = self._parse_txt(file_path)
            elif ext == '.pdf':
                result["parsed_text"] = self._parse_pdf(file_path)
            elif ext == '.docx':
                result["parsed_text"] = self._parse_docx(file_path)
            else:
                raise ValueError(f"Unsupported file type: {ext}")
            
            if not result["parsed_text"] or len(result["parsed_text"].strip()) < 50:
                result["status"] = "FAILED"
                result["error"] = "Extracted text is empty or too short to be a valid contract."
            else:
                result["status"] = "SUCCESS"

        except Exception as e:
            result["status"] = "FAILED"
            result["error"] = str(e)

        return result

    def _parse_txt(self, file_path: str) -> str:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()

    def _parse_pdf(self, file_path: str) -> str:
        text_blocks = []
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text_blocks.append(page_text)
        return "\n".join(text_blocks)

    def _parse_docx(self, file_path: str) -> str:
        doc = docx.Document(file_path)
        text_blocks = [para.text for para in doc.paragraphs if para.text.strip()]
        return "\n".join(text_blocks)

if __name__ == "__main__":
    pipeline = IngestionPipeline()
    
    test_path = os.path.join(os.path.dirname(__file__), "../contracts/sow_001_clean.txt")
    
    print(f"Testing ingestion on: {test_path}")
    output = pipeline.process(test_path)
    
    print("\n--- Ingestion Results ---")
    print(f"Status: {output['status']}")
    print(f"File Hash: {output['file_hash']}")
    
    if output['error']:
        print(f"Error: {output['error']}")
    else:
        print(f"Extracted Text (first 100 chars):\n{output['parsed_text'][:100]}...")