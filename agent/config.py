import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

MODEL = os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5")
MAX_TOKENS = 4096

# Runtime termination controls for the tool-calling loop in agent/loop.py.
# Defaults are set above measured traffic, not guessed: across the 419 captured
# agent_turn spans in docs/baseline/2026-07-19 and docs/experiments, the maximum
# observed iteration count is 3 and the maximum observed turn wall clock is 31.5s.
MAX_AGENT_ITERATIONS = int(os.getenv("MAX_AGENT_ITERATIONS", "8"))
AGENT_DEADLINE_SECONDS = float(os.getenv("AGENT_DEADLINE_SECONDS", "60"))

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
