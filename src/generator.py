from groq import AsyncGroq
import os
from dotenv import load_dotenv

load_dotenv()

class ClauseGenerator:
    def __init__(self):
        self.client = AsyncGroq()
        self.model = "openai/gpt-oss-120b"

    async def generate_alternative(self, risky_clause: str, category: str, explanation: str) -> str:
        """
        Generates a freelancer-friendly alternative to a risky clause.
        """
        system_prompt = """
        You are ClauseGuard, an expert legal AI specializing in protecting freelancers.
        The user has provided a risky contract clause, its risk category, and an explanation of why it is risky.
        
        Your task is to REWRITE the clause to be fair, balanced, and freelancer-friendly, while still being professional and acceptable to a reasonable client.
        
        CRITICAL RULES:
        1. Output ONLY the rewritten clause text.
        2. Do not include any introductory or concluding text (e.g., "Here is the rewritten clause:").
        3. Do not use markdown formatting like bolding or code blocks unless absolutely necessary for the legal text itself.
        4. Make it sound like standard, professional legal contract language.
        """
        
        user_prompt = f"""
        Risky Clause:
        {risky_clause}
        
        Risk Category: {category}
        Why it's risky: {explanation}
        
        Please provide the rewritten, safe clause:
        """
        
        try:
            response = await self.client.chat.completions.create(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                model=self.model,
                temperature=0.3,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            return f"Error generating alternative clause: {str(e)}"
