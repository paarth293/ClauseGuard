import asyncio
from src.analyzer import StructuredAnalyzer
from src.ingestion import IngestionPipeline

async def test():
    print("Testing Ingestion...")
    pipeline = IngestionPipeline()
    result = pipeline.process("contracts/sow_002_seeded.txt")
    text = result["parsed_text"]
    
    print("Testing Analyzer...")
    analyzer = StructuredAnalyzer()
    try:
        res = await analyzer.analyze(text)
        print("RESULT:")
        print(res)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test())
