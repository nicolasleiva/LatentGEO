import json
import logging
from typing import Dict, List, Any
from app.core.llm_kimi import get_llm_function

logger = logging.getLogger(__name__)

class ContentEditorService:
    def __init__(self):
        self.llm_function = get_llm_function()

    async def analyze_content(self, text: str, keyword: str) -> Dict[str, Any]:
        """
        Analyzes text content for GEO (Generative Engine Optimization) suitability using KIMI.
        """
        if not text or not keyword:
            return {"score": 0, "suggestions": [], "analysis": {}}

        prompt = f"""
        You are an expert in GEO (Generative Engine Optimization) and SEO. 
        Analyze the following text content targeting the keyword: "{keyword}".
        
        Your goal is to evaluate how likely this content is to be cited by an AI (like ChatGPT, Gemini, Perplexity) as a source.
        
        Evaluate based on these 4 GEO Pillars:
        1. **Direct Answer Capability**: Does it provide a concise, direct answer to the implicit question?
        2. **Structural Clarity**: Does it use lists, bold text, or clear headers that AIs can easily parse?
        3. **Authority & Data**: Does it use specific statistics, numbers, or authoritative citations?
        4. **Semantic Coverage**: Does it cover related entities and sub-topics naturally?

        Return a JSON object with this EXACT structure:
        {{
            "score": <integer_0_to_100>,
            "summary": "<short_one_sentence_summary>",
            "pillars": {{
                "direct_answer": {{ "score": <0-10>, "feedback": "<specific_feedback>" }},
                "structure": {{ "score": <0-10>, "feedback": "<specific_feedback>" }},
                "authority": {{ "score": <0-10>, "feedback": "<specific_feedback>" }},
                "semantics": {{ "score": <0-10>, "feedback": "<specific_feedback>" }}
            }},
            "suggestions": [
                {{ "type": "critical", "text": "<actionable_advice>" }},
                {{ "type": "improvement", "text": "<actionable_advice>" }}
            ],
            "missing_entities": ["<entity1>", "<entity2>", "<entity3>"]
        }}

        TEXT TO ANALYZE:
        {text[:4000]} 
        """

        try:
            response = await self.llm_function(prompt)
            
            # Clean response to ensure valid JSON
            cleaned_response = response.replace("```json", "").replace("```", "").strip()
            
            try:
                data = json.loads(cleaned_response)
                return data
            except json.JSONDecodeError:
                logger.error(f"Failed to parse LLM response: {cleaned_response}")
                # Fallback structure
                return {
                    "score": 50,
                    "summary": "Analysis completed but format was irregular.",
                    "pillars": {
                        "direct_answer": {"score": 5, "feedback": "Check manually."},
                        "structure": {"score": 5, "feedback": "Check manually."},
                        "authority": {"score": 5, "feedback": "Check manually."},
                        "semantics": {"score": 5, "feedback": "Check manually."}
                    },
                    "suggestions": [{"type": "info", "text": "Could not parse detailed AI response."}],
                    "missing_entities": []
                }

        except Exception as e:
            logger.error(f"Error in content analysis: {str(e)}")
            raise e
