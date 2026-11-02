import sys
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("vercel_entrypoint")

# Add project root to sys.path so app, config, agents, services are resolved cleanly
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

try:
    from app import app
except Exception as e:
    logger.exception("CRITICAL: Failed to import Flask application 'app': %s", e)
    raise
