import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

MODEL = os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5")
MAX_TOKENS = 4096

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
