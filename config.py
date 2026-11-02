import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


class Config:
    """Application configuration settings."""

    # Project paths
    BASE_DIR = BASE_DIR
    UPLOAD_FOLDER = BASE_DIR / "uploads"
    GENERATED_FOLDER = BASE_DIR / "generated_reports"

    # Security & Flask
    SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "dev-academic-assistant-secret-key-2026")
    DEBUG = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    PORT = int(os.getenv("FLASK_PORT", 5000))
    MAX_CONTENT_LENGTH = int(os.getenv("UPLOAD_MAX_FILE_SIZE_MB", 25)) * 1024 * 1024
    ALLOWED_EXTENSIONS = {"pdf"}

    # Groq LLM Configuration
    GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
    GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
    GROQ_FALLBACK_MODEL = os.getenv("GROQ_FALLBACK_MODEL", "qwen/qwen3.8-27b")

    # Search Configuration
    SEARCH_PROVIDER = os.getenv("SEARCH_PROVIDER", "duckduckgo").lower()
    TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")

    # Multi-Agent Workflow Defaults
    DEFAULT_CITATION_STYLE = os.getenv("DEFAULT_CITATION_STYLE", "IEEE")
    MAX_CORRECTION_ATTEMPTS = int(os.getenv("MAX_CORRECTION_ATTEMPTS", 3))
    EVALUATION_PASSING_SCORE = float(os.getenv("EVALUATION_PASSING_SCORE", 75.0))
    WORKFLOW_TIMEOUT_SECONDS = int(os.getenv("WORKFLOW_TIMEOUT_SECONDS", 300))

    # Supported citation styles
    SUPPORTED_CITATION_STYLES = ["IEEE", "APA", "MLA", "Chicago", "Harvard"]


# Ensure runtime directories exist
Config.UPLOAD_FOLDER.mkdir(exist_ok=True)
Config.GENERATED_FOLDER.mkdir(exist_ok=True)
