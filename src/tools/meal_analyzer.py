import base64
import json
from pathlib import Path
from openai import OpenAI
from src.config import OLLAMA_BASE_URL, VISION_MODEL
from src.utils.logger import get_logger
from src.utils.exception import MealAnalysisError

log = get_logger(__name__)


class MealAnalyzer:
    def __init__(self):
        self.client = OpenAI(
            base_url=OLLAMA_BASE_URL,
            api_key="not-needed",
        )
        self.model = VISION_MODEL
        log.debug("MealAnalyzer initialized with model=%s", self.model)

    def encode_image(self, image_path):
        image_path = Path(image_path)
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")

    def analyze(self, image_path):
        """
        Analyze a meal photo and return structured nutrition estimate.
        Returns dict with: foods, total_calories, protein, carbs, fat
        """
        log.info("Analyzing meal image: %s", image_path)
        base64_image = self.encode_image(image_path)

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
            temperature=0.1, # Low = deterministic, factual
        )

        raw = response.choices[0].message.content

        # Clean up common LLM JSON issues
        def clean_json(text):
            import re
            # Remove trailing commas before } or ]
            text = re.sub(r',\s*}', '}', text)
            text = re.sub(r',\s*]', ']', text)
            return text

        # Parse JSON from response
        try:
            result = json.loads(clean_json(raw))
            log.info(
                "Meal analyzed: %d kcal, %dg protein, %dg carbs, %dg fat | %s",
                result.get("total_calories", 0),
                result.get("total_protein_g", 0),
                result.get("total_carbs_g", 0),
                result.get("total_fat_g", 0),
                result.get("meal_description", "")[:60],
            )
            return result
        except json.JSONDecodeError:
            # Find JSON block in the response
            start = raw.find("{")
            end = raw.rfind("}") + 1
            if start != -1 and end > start:
                try:
                    result = json.loads(clean_json(raw[start:end]))
                    log.warning("JSON extracted from partial response for %s", image_path)
                    return result
                except json.JSONDecodeError:
                    pass
            # If all parsing fails, raise
            log.error("Failed to parse JSON response for image: %s", image_path)
            raise MealAnalysisError(f"Could not parse vision model response for {image_path}")