from prometheus_client import Counter, Histogram, Gauge, start_http_server

# Counters - things that only go up
MEALS_ANALYZED = Counter("fitagent_meals_analyzed_total", "Total meals analyzed", ["user_id"])
MEALS_LOGGED = Counter("fitagent_meals_logged_total", "Total meals logged", ["user_id"])
TOOL_CALLS = Counter("fitagent_tool_calls_total", "Tool calls by name", ["tool_name"])
ERRORS = Counter("fitagent_errors_total", "Errors by type", ["error_type"])

# Histograms - distribution of values
ANALYSIS_LATENCY = Histogram("fitagent_analysis_latency_seconds", "Meal analysis latency")
CALORIE_ESTIMATE = Histogram(
    "fitagent_calorie_estimate",
    "Distribution of calorie estimates",
    buckets=[100, 200, 300, 500, 700, 1000, 1500, 2000, 3000],
)

# Gauges - current values
ACTIVE_USERS = Gauge("fitagent_active_users", "Number of active users today")


def start_metrics_server(port=9090):
    """Start Prometheus metrics endpoint at /metrics."""
    start_http_server(port)
    print(f"Prometheus metrics available at http://localhost:{port}/metrics")