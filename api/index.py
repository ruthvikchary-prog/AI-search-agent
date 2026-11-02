import sys
import os
import logging
import traceback
from pathlib import Path

# Setup logging so Vercel shows errors in its Logs tab
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("vercel_entrypoint")

# Add project root to sys.path so app, config, agents, services are resolved cleanly
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

_import_error = None

try:
    from app import app
    logger.info("Flask app imported successfully.")
except Exception as exc:
    _import_error = traceback.format_exc()
    logger.error("CRITICAL: Failed to import Flask app: %s", _import_error)

    # Create a minimal fallback app so Vercel gets a 500 with the real error
    # instead of a completely opaque FUNCTION_INVOCATION_FAILED
    from flask import Flask, jsonify
    app = Flask(__name__)

    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    def import_error_handler(path):
        return jsonify({
            "error": "Application failed to start",
            "detail": _import_error
        }), 500
