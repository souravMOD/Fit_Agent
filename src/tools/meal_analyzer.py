import base64
import json
import re
import logging
from pathlib import Path
from openai import OpenAI
from src.config import (
    OLLAMA_BASE_URL, VISION_MODEL,
    DEPLOYMENT_MODE, GROQ_API_KEY, GROQ_BASE_URL, GROQ_VISION_MODEL,
)

log = logging.getLogger(__name__)


class MealAnalyzer:
    def __init__(self):
        if DEPLOYMENT_MODE == "cloud":
            self.client = OpenAI(
                base_url=GROQ_BASE_URL,
                api_key=GROQ_API_KEY,
            )
            self.model = GROQ_VISION_MODEL
            log.info(f"MealAnalyzer using Groq: {self.model}")
        else:
            self.client = OpenAI(
                base_url=OLLAMA_BASE_URL,
                api_key="not-needed",
            )
            self.model = VISION_MODEL
            log.info(f"MealAnalyzer using Ollama: {self.model}")

    def _encode_image(self, image_path):
        image_path = Path(image_path)
        if not image_path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")

    def _clean_json(self, text):
        """Fix common LLM JSON issues."""
        text = re.sub(r',\s*}', '}', text)
        text = re.sub(r',\s*]', ']', text)
        return text

    def _parse_response(self, raw):
        """Parse JSON from LLM response with multiple fallback strategies."""
        # Strategy 1: Direct parse
        try:
            return json.loads(self._clean_json(raw))
        except json.JSONDecodeError:
            pass

        # Strategy 2: Extract JSON block from surrounding text
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start != -1 and end > start:
            try:
                return json.loads(self._clean_json(raw[start:end]))
            except json.JSONDecodeError:
                pass

        # Strategy 3: Try to find JSON in markdown code blocks
        code_block = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', raw, re.DOTALL)
        if code_block:
            try:
                return json.loads(self._clean_json(code_block.group(1)))
            except json.JSONDecodeError:
                pass

        # All strategies failed
        log.warning("Could not parse JSON from response: %s", raw[:200])
        return {
            "foods": [],
            "total_calories": 0,
            "total_protein_g": 0,
            "total_carbs_g": 0,
            "total_fat_g": 0,
            "meal_description": raw[:500],
            "parse_error": True,
        }

    def analyze(self, image_path):
        """
        Analyze a meal photo and return structured nutrition estimate.
        Works with both Ollama (local) and Groq (cloud).

        Returns dict with: foods, total_calories, protein, carbs, fat
        """
        log.info("Analyzing meal image: %s (model: %s)", image_path, self.model)

        try:
            base64_image = self._encode_image(image_path)
        except FileNotFoundError as e:
            log.error("Image file not found: %s", image_path)
            raise

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": """Analyze this meal photo. Identify each food item and estimate its nutritional content.

Respond ONLY with this exact JSON format, no other text:
{
    "foods": [
        {"name": "food item name", "portion": "estimated portion size", "calories": 000, "protein_g": 00, "carbs_g": 00, "fat_g": 00}
    ],
    "total_calories": 000,
    "total_protein_g": 00,
    "total_carbs_g": 00,
    "total_fat_g": 00,
    "meal_description": "brief description of the overall meal"
}"""
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}"
                                }
                            }
                        ]
                    }
                ],
                temperature=0.1,
            )
        except Exception as e:
            log.error("LLM API call failed: %s", e)
            raise

        raw = response.choices[0].message.content
        log.debug("Raw LLM response: %s", raw[:300])

        result = self._parse_response(raw)

        if result.get("parse_error"):
            log.warning("JSON parse failed for %s", image_path)
        else:
            log.info("Analysis complete: %d cal, %d foods detected",
                     result.get("total_calories", 0),
                     len(result.get("foods", [])))

        return result