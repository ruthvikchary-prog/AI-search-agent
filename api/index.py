import sys
from pathlib import Path

# Add project root to sys.path so app, config, agents, services are resolved cleanly
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app import app
