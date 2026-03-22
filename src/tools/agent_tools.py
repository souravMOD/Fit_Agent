import json
import time
from langchain_core.tools import tool
from src.tools.meal_analyzer import MealAnalyzer
from src.database.meal_db import MealDatabase
from src.tracking.mlflow_tracker import FitAgentTracker
from src.utils.logger import get_logger
from src.utils.exception import MealAnalysisError, MealLoggingError, UserNotFoundError
from src.tracking.data_monitor import DataMonitor
from src.tracking.metrics import MEALS_ANALYZED, MEALS_LOGGED, ANALYSIS_LATENCY, CALORIE_ESTIMATE, ERRORS

monitor = DataMonitor()
log = get_logger(__name__)
tracker = FitAgentTracker()
db = MealDatabase()
analyzer = MealAnalyzer()

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
    log.info("analyze_and_log_meal called: image=%s type=%s user=%s", image_path, meal_type, _current_user_id)
    start_time = time.time()
    try:
        result = analyzer.analyze(image_path)
    except MealAnalysisError:
        ERRORS.labels(error_type="analysis").inc()
        raise
    except Exception as e:
        ERRORS.labels(error_type="analysis").inc()
        raise MealAnalysisError(f"Unexpected error analyzing {image_path}: {e}") from e
    latency = time.time() - start_time

    # Metrics for analysis
    ANALYSIS_LATENCY.observe(latency)
    CALORIE_ESTIMATE.observe(result.get("total_calories", 0))
    MEALS_ANALYZED.labels(user_id=str(_current_user_id)).inc()

    # Validate the analysis
    is_valid, warnings = monitor.validate_meal(result)
    if warnings:
        log.warning("Meal validation warnings: %s", warnings)
        result["warnings"] = warnings

    # Log to WhyLogs monitor
    try:
        monitor.log_meal_analysis(result)
    except Exception as e:
        log.warning("WhyLogs monitoring failed: %s", e)

    # Log to database
    try:
        db.log_meal(_current_user_id, result, meal_type=meal_type)
        MEALS_LOGGED.labels(user_id=str(_current_user_id)).inc()
    except Exception as e:
        ERRORS.labels(error_type="database").inc()
        raise MealLoggingError(f"Failed to log meal for user {_current_user_id}: {e}") from e
    log.info("Meal logged to DB for user %s (%.2fs)", _current_user_id, latency)

    # Track with MLflow
    try:
        tracker.log_meal_analysis(image_path, result, latency)
    except Exception as e:
        log.warning("MLflow tracking failed: %s", e)

    result["status"] = "analyzed_and_logged"
    return json.dumps(result, indent=2)


@tool
def log_meal_manually(calories: int, protein_g: int, carbs_g: int, fat_g: int, description: str, meal_type: str = "meal") -> str:
    """Log a meal manually without a photo.
    Use this when the user tells you what they ate without sending an image.
    Args:
        calories: Total calories
        protein_g: Grams of protein
        carbs_g: Grams of carbs
        fat_g: Grams of fat
        description: Brief description of the meal
        meal_type: One of breakfast, lunch, dinner, snack
    """
    log.info("log_meal_manually called: %s %d cal user=%s", description, calories, _current_user_id)
    analysis = {
        "total_calories": calories,
        "total_protein_g": protein_g,
        "total_carbs_g": carbs_g,
        "total_fat_g": fat_g,
        "foods": [],
        "meal_description": description,
    }
    try:
        result = db.log_meal(_current_user_id, analysis, meal_type=meal_type)
        MEALS_LOGGED.labels(user_id=str(_current_user_id)).inc()
    except Exception as e:
        ERRORS.labels(error_type="database").inc()
        raise MealLoggingError(f"Failed to log meal: {e}") from e
    return json.dumps(result)


@tool
def get_daily_summary() -> str:
    """Get today's nutrition summary.
    Use this when the user asks about today's intake or progress.
    """
    log.debug("get_daily_summary called for user %s", _current_user_id)
    summary = db.get_daily_summary(_current_user_id)
    return json.dumps(summary, indent=2)


@tool
def get_weekly_history() -> str:
    """Get the last 7 days of nutrition data.
    Use this when the user asks about their week or trends.
    """
    log.debug("get_weekly_history called for user %s", _current_user_id)
    history = db.get_weekly_history(_current_user_id)
    return json.dumps(history, indent=2)


@tool
def check_goals() -> str:
    """Check how current daily intake compares to targets.
    Use this to give feedback on whether the user is on track.
    """
    log.debug("check_goals called for user %s", _current_user_id)
    try:
        targets = db.get_user_targets(_current_user_id)
    except UserNotFoundError:
        log.warning("check_goals: user %s not found", _current_user_id)
        return json.dumps({"error": "User not found"})
    summary = db.get_daily_summary(_current_user_id)

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


@tool
def correct_last_meal(calories: int = None, protein_g: int = None, carbs_g: int = None, fat_g: int = None) -> str:
    """Correct the most recently logged meal's nutrition values.
    Use this when the user says the calorie estimate was wrong or wants to update their last meal.
    Args:
        calories: Corrected total calories (optional)
        protein_g: Corrected protein in grams (optional)
        carbs_g: Corrected carbs in grams (optional)
        fat_g: Corrected fat in grams (optional)
    """
    import sqlite3
    log.info("correct_last_meal called for user %s", _current_user_id)
    conn = sqlite3.connect(db.db_path)
    cursor = conn.execute(
        "SELECT id, total_calories, total_protein_g, total_carbs_g, total_fat_g, meal_description FROM meals WHERE user_id = ? ORDER BY id DESC LIMIT 1",
        (_current_user_id,),
    )
    row = cursor.fetchone()
    if not row:
        conn.close()
        return json.dumps({"error": "No meals found to correct"})

    meal_id = row[0]
    old_cal = row[1]

    new_cal = calories if calories is not None else row[1]
    new_pro = protein_g if protein_g is not None else row[2]
    new_carb = carbs_g if carbs_g is not None else row[3]
    new_fat = fat_g if fat_g is not None else row[4]

    conn.execute(
        "UPDATE meals SET total_calories=?, total_protein_g=?, total_carbs_g=?, total_fat_g=? WHERE id=?",
        (new_cal, new_pro, new_carb, new_fat, meal_id),
    )
    conn.commit()
    conn.close()

    log.info("Meal corrected: %d -> %d cal", old_cal, new_cal)
    return json.dumps({
        "status": "corrected",
        "meal": row[5],
        "old_calories": old_cal,
        "new_calories": new_cal,
    })


@tool
def get_meal_history(limit: int = 5) -> str:
    """Get the most recent meals with details.
    Use this when the user asks about their recent meals or meal history.
    Args:
        limit: Number of recent meals to return
    """
    import sqlite3
    log.debug("get_meal_history called for user %s", _current_user_id)
    conn = sqlite3.connect(db.db_path)
    cursor = conn.execute(
        """SELECT total_calories, total_protein_g, total_carbs_g, total_fat_g,
                  meal_description, meal_type, timestamp, image_path
           FROM meals WHERE user_id = ? ORDER BY id DESC LIMIT ?""",
        (_current_user_id, limit),
    )
    meals = cursor.fetchall()
    conn.close()

    history = []
    for m in meals:
        history.append({
            "calories": m[0],
            "protein_g": m[1],
            "carbs_g": m[2],
            "fat_g": m[3],
            "description": m[4],
            "meal_type": m[5],
            "time": m[6],
            "image_path": m[7],
        })

    return json.dumps(history, indent=2)