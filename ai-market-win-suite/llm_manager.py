import os
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

class LLMBrain:
    def __init__(self):
        # Groq API Client setup
        # Note: Agar API key setup nahi hai toh error handle karne ke liye fallback handling lagayi hai
        api_key = os.getenv("GROQ_API_KEY", "mock_key_if_not_present")
        self.client = Groq(api_key=api_key)
        self.model = "qwen3-32b"  # Recommended high-speed hackathon model[span_2](start_span)[span_2](end_span)

    def generate_winning_proposal(self, rfp_text, recalled_memories):
        """Hindsight memory aur client requirements ko combine karke dynamic proposal banta hai"""
        
        # Recalled memories ko ek single context string mein parse kar rahe hain
        memory_context = "\n".join([m.text for m in recalled_memories]) if recalled_memories else "No previous competitor constraints logged."
        
        system_prompt = (
            "You are an elite B2B Sales Proposal Engineer. Your objective is to write a strategic project proposal. "
            "CRITICAL STRATEGY: Analyze the provided Market Intelligence Memory (Hindsight Layer). If it mentions specific "
            "competitor vulnerabilities, pricing drops, or support failures, write our solution proposal to aggressively "
            "counter those weaknesses without mentioning the competitor name aggressively. Make our delivery look superior."
        )
        
        user_prompt = f"""
        CLIENT RFP REQUIREMENTS:
        {rfp_text}
        
        MARKET INTELLIGENCE ANALYSIS (HINDSIGHT LAYER):
        {memory_context}
        
        Generate a highly polished, line-by-line professional B2B executive proposal matching client pain points.
        """
        
        # Check if real API key is missing to avoid backend crash during testing
        if os.getenv("GROQ_API_KEY") is None or os.getenv("GROQ_API_KEY") == "your_groq_api_key_here":
            return (
                f"### ✨ [MOCK MODE] Generated B2B Strategic Proposal\n\n"
                f"**Executive Summary:** We acknowledge your requirement for: *\"{rfp_text}\"*.\n\n"
                f"**Our Strategic Advantage:** Based on our historical market engine updates ({memory_context}), "
                f"our system explicitly guarantees fixed pricing architecture and a robust 24/7 priority support layer "
                f"that completely mitigates standard industry downtime risks. \n\n"
                f"*(Note: Provide a valid GROQ_API_KEY in your .env file to see real-time dynamic AI outputs!)*"
            )

        try:
            response = self.client.chat.completions.create(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                model=self.model,
                temperature=0.3
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"⚠️ Error in Groq LLM Function Call Execution: {str(e)}"