class RiskScorer:
    """
    Calculates a safety score for a contract based on the extracted risks.
    Starts at 100.
    must_raise = -15 points
    worth_raising = -5 points
    Minimum score is 0.
    """
    def calculate_score(self, findings: list) -> int:
        score = 100
        
        for finding in findings:
            severity = finding.get("severity", "worth_raising").lower()
            if severity == "must_raise":
                score -= 15
            elif severity == "worth_raising":
                score -= 5
            else:
                score -= 5 # default penalty for any flagged risk
                
        # Ensure score stays between 0 and 100
        return max(0, min(100, score))
