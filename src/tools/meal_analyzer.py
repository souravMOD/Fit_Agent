import base64
import json
from pathlib import Path
from openai import OpenAI
from src.config import OLLAMA_BASE_URL, VISION_MODEL


class MealAnalyzer:
    def __init__(self):
        self.client = OpenAI(
            base_url=OLLAMA_BASE_URL,
            api_key="not-needed",
        )
        self.model = VISION_MODEL

    def encode_image(self, image_path):
        image_path = Path(image_path)
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")

    def analyze(self, image_path):
        """
        Analyze a meal photo and return structured nutrition estimate.
        Returns dict with: foods, total_calories, protein, carbs, fat
        """
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

        # Parse JSON from response (LLaVA sometimes adds extra text)
        try:
            # Try direct parse first
            return json.loads(raw)
        except json.JSONDecodeError:
            # Find JSON block in the response
            start = raw.find("{")
            end = raw.rfind("}") + 1
            if start != -1 and end > start:
                return json.loads(raw[start:end])
            # If all parsing fails, return raw as description
            return {
                "foods": [],
                "total_calories": 0,
                "total_protein_g": 0,
                "total_carbs_g": 0,
                "total_fat_g": 0,
                "meal_description": raw,
                "parse_error": True,
            }