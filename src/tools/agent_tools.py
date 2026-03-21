import json
from langchain_core.tools import tool
from src.tools.meal_analyzer import MealAnalyzer
from src.database.meal_db import MealDatabase
import time
from src.tracking.mlflow_tracker import FitAgentTracker

tracker = FitAgentTracker()

db = MealDatabase()
analyzer = MealAnalyzer()

# This gets set before each agent call
_current_user_id = 1


def set_current_user(user_id):
    global _current_user_id
    _current_user_id = user_id


@tool
def analyze_and_log_meal(image_path: str, meal_type: str = "meal") -> str:
    """Analyze a meal photo, estimate nutrition, and log it to the database.
    Use this when the user sends a food image or says they ate something.
    Args:
        image_path: Path to the meal image file
        meal_type: One of breakfast, lunch, dinner, snack
    """
    start_time = time.time()
    result = analyzer.analyze(image_path)
    latency = time.time() - start_time

    # Log to database
    db.log_meal(_current_user_id, result, meal_type=meal_type)

    # Track with MLflow
    tracker.log_meal_analysis(image_path, result, latency)

    result["status"] = "analyzed_and_logged"
    return json.dumps(result, indent=2)

@tool
def log_meal(calories: int, protein_g: int, carbs_g: int, fat_g: int, description: str, meal_type: str = "meal") -> str:
    """Log a meal to the database after analyzing it.
    Use this after analyze_meal_image to save the results.
    Args:
        calories: Total calories
        protein_g: Grams of protein
        carbs_g: Grams of carbs
        fat_g: Grams of fat
        description: Brief description of the meal
        meal_type: One of breakfast, lunch, dinner, snack
    """
    analysis = {
        "total_calories": calories,
        "total_protein_g": protein_g,
        "total_carbs_g": carbs_g,
        "total_fat_g": fat_g,
        "foods": [],
        "meal_description": description,
    }
    result = db.log_meal(_current_user_id, analysis, meal_type=meal_type)
    return json.dumps(result)


@tool
def get_daily_summary() -> str:
    """Get today's nutrition summary.
    Use this when the user asks about today's intake or progress.
    """
    summary = db.get_daily_summary(_current_user_id)
    return json.dumps(summary, indent=2)

@tool
def get_weekly_history() -> str:
    """Get the last 7 days of nutrition data.
    Use this when the user asks about their week or trends.
    """
    history = db.get_weekly_history(_current_user_id)
    return json.dumps(history, indent=2)


@tool
def check_goals() -> str:
    """Check how current daily intake compares to targets.
    Use this to give feedback on whether the user is on track.
    """
    targets = db.get_user_targets(_current_user_id)
    summary = db.get_daily_summary(_current_user_id)

    if not targets:
        return json.dumps({"error": "User not found"})

    remaining = {
        "calories_remaining": targets["calorie_target"] - summary["total_calories"],
        "protein_remaining_g": targets["protein_target"] - summary["total_protein_g"],
        "carbs_remaining_g": targets["carbs_target"] - summary["total_carbs_g"],
        "fat_remaining_g": targets["fat_target"] - summary["total_fat_g"],
        "meals_logged_today": summary["meal_count"],
        "targets": targets,
        "current": {
            "calories": summary["total_calories"],
            "protein_g": summary["total_protein_g"],
            "carbs_g": summary["total_carbs_g"],
            "fat_g": summary["total_fat_g"],
        },
    }
    return json.dumps(remaining, indent=2)