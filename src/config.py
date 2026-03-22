import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
MEAL_IMAGES_DIR = DATA_DIR / "meal_images"
DB_PATH = DATA_DIR / "fitagent.db"

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
VISION_MODEL = os.getenv("VISION_MODEL", "llava:7b")
LLM_MODEL = os.getenv("LLM_MODEL", "llama3.1:8b")

# Your personal nutrition targets (adjust to your goals)
DAILY_CALORIE_TARGET = int(os.getenv("DAILY_CALORIE_TARGET", "2200"))
DAILY_PROTEIN_TARGET = int(os.getenv("DAILY_PROTEIN_TARGET", "150"))
DAILY_CARBS_TARGET = int(os.getenv("DAILY_CARBS_TARGET", "250"))
DAILY_FAT_TARGET = int(os.getenv("DAILY_FAT_TARGET", "70"))
LLM_TEMPERATURE= float(os.getenv("LLM_TEMPERATURE", "0.1"))
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
# Deployment mode: "local" (Ollama) or "cloud" (Groq)
DEPLOYMENT_MODE = os.getenv("DEPLOYMENT_MODE", "local")

# Groq (free cloud API)
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_BASE_URL = "https://api.groq.com/openai/v1"
GROQ_VISION_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"
GROQ_LLM_MODEL = "llama-3.3-70b-versatile"