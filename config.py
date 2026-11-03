"""Configuration settings for Mars Base Multi-Agent Mission Control."""

import os
from pathlib import Path
from dotenv import load_dotenv, find_dotenv

# Load .env file
load_dotenv(find_dotenv(usecwd=True))

# LLM / Groq Configuration
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_BASE_URL = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")

# Mission Parameters
TOTAL_SOLS = 5
MAX_REVIEW_TRIES = 3

# Valid repair targets accepted by the Mars Base Simulator
VALID_REPAIR_TARGETS = [
    "oxygen_generator",
    "air_scrubber",
    "oxygen_sensor",
    "battery_bank",
    "solar_panels",
    "electrical_grid",
]

# File Paths
WORKSPACE_DIR = Path(__file__).resolve().parent
MISSION_LOG_PATH = WORKSPACE_DIR / "mission_log.json"
MISSION_STATE_PATH = WORKSPACE_DIR / "mission_state.json"
