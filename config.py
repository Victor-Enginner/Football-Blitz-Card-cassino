"""Football Blitz Command Center — configuration (env-only, no secrets in code)."""
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent / ".env")
except ImportError:
    pass

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.getenv("FB_DATA_DIR", BASE_DIR / "data"))
DB_PATH = DATA_DIR / os.getenv("FB_DB_NAME", "command_center.db")

# --- AI gateway (OmniRoute primary) -----------------------------------------
# Explicit opt-in until a remote free provider is configured and validated.
# User preference: no Ollama/local inference and no implicit paid fallback.
REMOTE_LLM_ENABLED = os.getenv("FB_REMOTE_LLM_ENABLED", "false").lower() in ("1", "true", "yes")
OMNIROUTE_BASE_URL = os.getenv("OMNIROUTE_BASE_URL", "http://localhost:20128").rstrip("/")
OMNIROUTE_MODEL = os.getenv("OMNIROUTE_MODEL", "auto")
OMNIROUTE_TIMEOUT_S = float(os.getenv("OMNIROUTE_TIMEOUT_S", "60"))
OMNIROUTE_API_KEY = os.getenv("OMNIROUTE_API_KEY", "").strip()  # optional; gateway usually needs none locally
HERMES_ENDPOINT = os.getenv("HERMES_ENDPOINT", "").strip()  # TokenRouter/OpenAI-compatible endpoint for hermes-agent
OMNIROUTE_HEALTH = {"enabled": True, "base_url": OMNIROUTE_BASE_URL, "model": OMNIROUTE_MODEL}

# --- AIsa (verified provider, OpenAI-compatible) -------------------------------
AISA_ENABLED = os.getenv("AISA_ENABLED", "false").lower() in ("1", "true", "yes")
AISA_BASE_URL = os.getenv("AISA_BASE_URL", "https://api.aisa.one").rstrip("/")
AISA_MODEL = os.getenv("AISA_MODEL", "claude-haiku-4-5-20251001")
AISA_API_KEY = os.getenv("AISA_API_KEY", "").strip()

# --- TokenRouter (free tier, OpenAI-compatible; e.g. z-ai/glm-5.3-free) --------
TOKENROUTER_ENABLED = os.getenv("TOKENROUTER_ENABLED", "true").lower() in ("1", "true", "yes")
TOKENROUTER_BASE_URL = os.getenv("TOKENROUTER_BASE_URL", "https://api.tokenrouter.com").rstrip("/")
TOKENROUTER_MODEL = os.getenv("TOKENROUTER_MODEL", "z-ai/glm-5.3-free")
TOKENROUTER_API_KEY = os.getenv("TOKENROUTER_API_KEY", "").strip()

# --- NVIDIA NIM (free tier, OpenAI-compatible; integrate.api.nvidia.com) -------
NVIDIA_ENABLED = os.getenv("NVIDIA_ENABLED", "true").lower() in ("1", "true", "yes")
NVIDIA_BASE_URL = os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com").rstrip("/")
NVIDIA_MODEL = os.getenv("NVIDIA_MODEL", "meta/llama-3.3-70b-instruct")
NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY", "").strip()

# --- Generic provider slot (for 9route or any verified OpenAI-compatible API) --
GENERIC_PROVIDER_ENABLED = os.getenv("GENERIC_PROVIDER_ENABLED", "false").lower() in ("1", "true", "yes")
GENERIC_PROVIDER_BASE_URL = os.getenv("GENERIC_PROVIDER_BASE_URL", "").rstrip("/")
GENERIC_PROVIDER_MODEL = os.getenv("GENERIC_PROVIDER_MODEL", "")
GENERIC_PROVIDER_API_KEY = os.getenv("GENERIC_PROVIDER_API_KEY", "").strip()
GENERIC_PROVIDER_NAME = os.getenv("GENERIC_PROVIDER_NAME", "generic-slot")

# --- Compression -------------------------------------------------------------
COMPRESSION_ENABLED = os.getenv("FB_COMPRESSION", "true").lower() in ("1", "true", "yes")
COMPRESSION_TARGET_RATIO = float(os.getenv("FB_COMPRESSION_TARGET", "0.55"))  # keep <= 55% of original
COMPRESSION_MIN_CHARS = int(os.getenv("FB_COMPRESSION_MIN_CHARS", "400"))

# --- Governance: limits (all local, all blocking) -----------------------------
MAX_EVENTS_PER_DAY = int(os.getenv("FB_MAX_EVENTS_PER_DAY", "200"))  # daily volume hard limit
STOP_LOSS = float(os.getenv("FB_STOP_LOSS", "75.0"))                 # paper loss cap per day
STOP_WIN = float(os.getenv("FB_STOP_WIN", "0.0"))                    # 0 = disabled
MAX_SESSION_MINUTES = int(os.getenv("FB_MAX_SESSION_MINUTES", "60"))
COOLDOWN_MINUTES = int(os.getenv("FB_COOLDOWN_MINUTES", "30"))
HOT_STREAK_ALERT = int(os.getenv("FB_HOT_STREAK", "10"))             # repeated-outcome alert threshold

# --- Telegram (bot via @BotFather; unset = notifier is a no-op) ---------------
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()

# --- Observer bridge (game events from your local machine) -------------------
# Set OBSERVER_TOKEN to require auth on /ws and /api/ingest (recommended on VPS).
OBSERVER_TOKEN = os.getenv("OBSERVER_TOKEN", "").strip()

# --- Behaviour ---------------------------------------------------------------
AI_COPILOT_ENABLED = os.getenv("FB_AI_COPILOT", "true").lower() in ("1", "true", "yes")
MAX_HYPOTHESES = int(os.getenv("FB_MAX_HYPOTHESES", "50"))

# --- Operational states (no AUTO_EXECUTION exists, ever) ----------------------
STATES = ("OFFLINE", "PAPER", "MANUAL_REVIEW", "COOLDOWN", "STOPPED")
DATA_ORIGINS = ("manual", "fixture", "authorized_readonly", "simulated")


def ensure_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


ensure_dirs()
