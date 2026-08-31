"""
Contract Chatbot — Uses GPT-4o-mini for fast Q&A over contract text.
"""

from .llm import get_openai_client, get_model


class ContractChatbot:
    def __init__(self):
        self.client = get_openai_client()
        self.model = get_model("chat")  # gpt-4o-mini

    async def answer_question(self, contract_text: str, question: str) -> str:
        """
        Answers a user's question based on the contract context.
        """
        system_prompt = """
        You are ClauseGuard AI, an expert legal assistant. 
        Your job is to answer the user's questions about their contract.
        
        RULES:
        1. Base your answer ONLY on the provided contract text.
        2. If the contract doesn't contain the answer, explicitly state that you cannot find it in the contract.
        3. Be clear, concise, and professional.
        4. Explain legal jargon in plain English.
        """
        
        user_prompt = f"""
=== CONTRACT TEXT ===
{contract_text}
=====================

User Question: {question}
"""
        
        try:
            response = await self.client.chat.completions.create(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                model=self.model,
                temperature=0.2,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            return f"Error connecting to Chatbot API: {str(e)}"
