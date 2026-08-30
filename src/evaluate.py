import os
import pandas as pd
from ingestion import IngestionPipeline
from analyzer import StructuredAnalyzer
from verifier import DeterministicVerifier
from semantic_verifier import SemanticVerifier

def run_evaluation():
    print("Starting ClauseGuard Evaluation Protocol...")
    tracker_path = os.path.join(os.path.dirname(__file__), "../data/tracker.csv")
    
    # Load our Ground Truth answer key
    df = pd.read_csv(tracker_path)
    
    true_positives = 0
    false_positives = 0
    false_negatives = 0
    
    # Group the CSV by contract so we only process each file once
    contracts = df['contract_id'].unique()
    
    for contract in contracts:
        print(f"\nEvaluating {contract}...")
        file_path = os.path.join(os.path.dirname(__file__), f"../contracts/{contract}")
        
        if not os.path.exists(file_path):
            print(f"  Skipping: File not found ({contract})")
            continue
            
        # Run the AI pipeline silently (no print statements)
        parsed_text = IngestionPipeline().process(file_path)["parsed_text"]
        raw_findings = StructuredAnalyzer().analyze(parsed_text).get("findings", [])
        det_verified = DeterministicVerifier().verify(raw_findings, parsed_text)
        final_findings = SemanticVerifier().verify_interpretation(det_verified)
        
        # What risks did the CSV say we should find?
        expected_categories = df[df['contract_id'] == contract]['risk_type'].tolist()
        
        # What risks did the AI actually find?
        found_categories = [f.get("category") for f in final_findings]
        
        # Compare them to calculate our score
        for expected in expected_categories:
            if expected in found_categories:
                true_positives += 1
                found_categories.remove(expected) # Mark as found
            else:
                false_negatives += 1
                print(f"  ❌ MISSED: {expected}")
                
        # Any risks the AI found that weren't in the CSV are False Positives
        for hallucination in found_categories:
            false_positives += 1
            print(f"  ⚠️ HALLUCINATION: {hallucination}")
            
    # Final Math
    total_expected = true_positives + false_negatives
    total_found = true_positives + false_positives
    
    # Avoid dividing by zero if the dataset is empty
    recall = (true_positives / total_expected) * 100 if total_expected > 0 else 100
    precision = (true_positives / total_found) * 100 if total_found > 0 else 100
    
    print("\n" + "="*50)
    print(" FINAL EVALUATION METRICS")
    print("="*50)
    print(f"Total True Positives (Caught Risks): {true_positives}")
    print(f"Total False Negatives (Missed Risks): {false_negatives}")
    print(f"Total False Positives (Hallucinations): {false_positives}")
    print("-" * 50)
    print(f"RECALL:    {recall:.1f}% (Core promise: Not missing things)")
    print(f"PRECISION: {precision:.1f}% (Core promise: Not inventing things)")
    print("="*50)

if __name__ == "__main__":
    run_evaluation()