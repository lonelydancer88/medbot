import os
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_API_URL = os.getenv("ANTHROPIC_API_URL", "")
LLM_MODEL = os.getenv("LLM_MODEL", "deepseek-v4-flash")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./medbot.db")
