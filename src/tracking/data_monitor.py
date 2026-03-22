import os
os.environ["WHYLOGS_NO_ANALYTICS"] = "true"

import whylogs as why
import json
import logging
from datetime import datetime
from pathlib import Path
from src.config import DATA_DIR

log = logging.getLogger(__name__)

PROFILES_DIR = DATA_DIR / "whylogs_profiles"
PROFILES_DIR.mkdir(parents=True, exist_ok=True)


class DataMonitor:
    def __init__(self):
        self.daily_data = []

    def log_meal_analysis(self, analysis):
        """Log a single meal analysis for profiling."""
        row = {
            "calories": analysis.get("total_calories", 0),
            "protein_g": analysis.get("total_protein_g", 0),
            "carbs_g": analysis.get("total_carbs_g", 0),
            "fat_g": analysis.get("total_fat_g", 0),
            "num_foods": len(analysis.get("foods", [])),
            "parse_error": 1 if analysis.get("parse_error") else 0,
        }
        self.daily_data.append(row)
        log.info(f"WhyLogs: logged meal data point ({len(self.daily_data)} today)")

    def generate_profile(self):
        """Generate a WhyLogs profile from today's data."""
        if not self.daily_data:
            log.info("No data to profile")
            return None

        results = why.log(self.daily_data)
        profile = results.profile()

        # Save profile
        today = datetime.now().strftime("%Y-%m-%d")
        profile_path = PROFILES_DIR / f"profile_{today}.bin"
        profile.write(str(profile_path))
        log.info(f"WhyLogs profile saved: {profile_path}")

        return profile

    def validate_meal(self, analysis):
        """
        Check if a meal analysis looks reasonable.
        Returns (is_valid, warnings)
        """
        warnings = []
        calories = analysis.get("total_calories", 0)
        protein = analysis.get("total_protein_g", 0)
        carbs = analysis.get("total_carbs_g", 0)
        fat = analysis.get("total_fat_g", 0)

        # Sanity checks
        if calories <= 0:
            warnings.append("Calorie estimate is zero or negative")
        if calories > 5000:
            warnings.append(f"Unusually high calories: {calories}")
        if protein + carbs + fat == 0:
            warnings.append("All macros are zero")
        if calories > 0 and abs(calories - (protein * 4 + carbs * 4 + fat * 9)) > 200:
            warnings.append("Macro breakdown doesn't match total calories")
        if analysis.get("parse_error"):
            warnings.append("LLaVA response could not be parsed as JSON")
        if len(analysis.get("foods", [])) == 0:
            warnings.append("No individual foods detected")

        is_valid = len(warnings) == 0
        return is_valid, warnings

    def get_daily_stats(self):
        """Return summary statistics for today's analyses."""
        if not self.daily_data:
            return {"message": "No data today"}

        calories = [d["calories"] for d in self.daily_data]
        return {
            "analyses_today": len(self.daily_data),
            "avg_calories": sum(calories) / len(calories),
            "min_calories": min(calories),
            "max_calories": max(calories),
            "parse_errors": sum(d["parse_error"] for d in self.daily_data),
        }