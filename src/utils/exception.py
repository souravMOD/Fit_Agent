class FitAgentError(Exception):
    """Base exception for all fit-agent errors."""


class MealAnalysisError(FitAgentError):
    """Raised when meal image analysis fails or returns unreadable output."""


class MealLoggingError(FitAgentError):
    """Raised when a meal cannot be saved to the database."""


class DatabaseError(FitAgentError):
    """Raised on unexpected database errors."""


class UserNotFoundError(FitAgentError):
    """Raised when a user_id has no matching record."""


class AgentError(FitAgentError):
    """Raised when the LangGraph agent encounters an unrecoverable error."""


class TrackingError(FitAgentError):
    """Raised when MLflow tracking fails in a way that should be surfaced."""
