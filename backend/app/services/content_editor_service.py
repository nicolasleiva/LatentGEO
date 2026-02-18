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

        system_prompt = """
        You are an expert in GEO (Generative Engine Optimization) and SEO.
        Evaluate content quality for AI citation probability.

        Return a JSON object with this EXACT structure:
        {
            "score": <integer_0_to_100>,
            "summary": "<short_one_sentence_summary>",
            "pillars": {
                "direct_answer": { "score": <0-10>, "feedback": "<specific_feedback>" },
                "structure": { "score": <0-10>, "feedback": "<specific_feedback>" },
                "authority": { "score": <0-10>, "feedback": "<specific_feedback>" },
                "semantics": { "score": <0-10>, "feedback": "<specific_feedback>" }
            },
            "suggestions": [
                { "type": "critical", "text": "<actionable_advice>" },
                { "type": "improvement", "text": "<actionable_advice>" }
            ],
            "missing_entities": ["<entity1>", "<entity2>", "<entity3>"]
        }
        """
        user_prompt = f"""
        Analyze the following text content targeting the keyword: "{keyword}".

        Your goal is to evaluate how likely this content is to be cited by an AI
        (like ChatGPT, Gemini, Perplexity) as a source.

        Evaluate using these 4 GEO pillars:
        1. Direct Answer Capability
        2. Structural Clarity
        3. Authority & Data
        4. Semantic Coverage

        TEXT TO ANALYZE:
        {text[:4000]}
        """

        try:
            response = await self.llm_function(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
            )
            
            # Clean response to ensure valid JSON
            cleaned_response = str(response).replace("```json", "").replace("```", "").strip()
            
            try:
                data = json.loads(cleaned_response)
                return data
            except json.JSONDecodeError:
                logger.error(f"Failed to parse LLM response: {cleaned_response}")
                # Deterministic non-fabricated fallback
                return {
                    "score": 0,
                    "status": "insufficient_data",
                    "summary": "The model response was not valid JSON; no reliable analysis was produced.",
                    "pillars": {
                        "direct_answer": {"score": 0, "feedback": "Insufficient data."},
                        "structure": {"score": 0, "feedback": "Insufficient data."},
                        "authority": {"score": 0, "feedback": "Insufficient data."},
                        "semantics": {"score": 0, "feedback": "Insufficient data."}
                    },
                    "suggestions": [
                        {
                            "type": "error",
                            "text": "Retry analysis after confirming model output format.",
                        }
                    ],
                    "missing_entities": []
                }

        except Exception as e:
            logger.error(f"Error in content analysis: {str(e)}")
            raise e
