import mlflow
import time
from datetime import datetime
from src.utils.logger import get_logger

log = get_logger(__name__)


class FitAgentTracker:
    def __init__(self, experiment_name="fitagent"):
        mlflow.set_experiment(experiment_name)
        log.debug("MLflow experiment set to '%s'", experiment_name)

    def log_meal_analysis(self, image_path, analysis, latency_seconds):
        """Log each meal analysis for tracking LLaVA performance."""
        with mlflow.start_run(run_name=f"meal_{datetime.now().strftime('%Y%m%d_%H%M%S')}"):
            # Metrics
            mlflow.log_metric("calories", analysis.get("total_calories", 0))
            mlflow.log_metric("protein_g", analysis.get("total_protein_g", 0))
            mlflow.log_metric("carbs_g", analysis.get("total_carbs_g", 0))
            mlflow.log_metric("fat_g", analysis.get("total_fat_g", 0))
            mlflow.log_metric("num_foods_detected", len(analysis.get("foods", [])))
            mlflow.log_metric("latency_seconds", latency_seconds)
            mlflow.log_metric("parse_error", 1 if analysis.get("parse_error") else 0)

            # Parameters
            mlflow.log_param("model", "llava:7b")
            mlflow.log_param("image_path", str(image_path))
            mlflow.log_param("meal_description", analysis.get("meal_description", "")[:200])

            # Log the image as artifact
            try:
                mlflow.log_artifact(str(image_path))
            except Exception as e:
                log.warning("Could not log image artifact to MLflow: %s", e)

    def log_agent_interaction(self, user_query, tools_called, response_length, latency_seconds):
        """Log agent interactions for monitoring tool usage patterns."""
        log.info("Agent interaction: tools=%s latency=%.2fs", tools_called, latency_seconds)
        with mlflow.start_run(run_name=f"agent_{datetime.now().strftime('%Y%m%d_%H%M%S')}"):
            mlflow.log_metric("response_length", response_length)
            mlflow.log_metric("latency_seconds", latency_seconds)
            mlflow.log_metric("num_tools_called", len(tools_called))

            mlflow.log_param("user_query", user_query[:200])
            mlflow.log_param("tools_called", ",".join(tools_called))
            mlflow.log_param("model", "llama3.1:8b")