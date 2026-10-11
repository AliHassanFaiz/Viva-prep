"""All environment variables and tunable thresholds live here (SPEC section 3)."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- keys / services ---
    GROQ_API_KEY: str = ""
    ELEVENLABS_API_KEY: str = ""
    ELEVENLABS_VOICE_ID: str = ""
    ELEVENLABS_MODEL: str = "eleven_flash_v2_5"
    QDRANT_URL: str = ""
    QDRANT_API_KEY: str = ""
    QDRANT_COLLECTION: str = "viva_chunks"
    DATABASE_URL: str = ""
    ALLOWED_ORIGINS: str = "http://localhost:5173"

    # --- models ---
    MODEL_QUESTIONS: str = "openai/gpt-oss-20b"
    MODEL_DECISION: str = "openai/gpt-oss-120b"
    MODEL_DECISION_FALLBACK: str = "openai/gpt-oss-20b"
    MODEL_REPORT: str = "qwen/qwen3.8-27b"
    MODEL_STT: str = "whisper-large-v3-turbo"
    EMBED_MODEL: str = "BAAI/bge-small-en-v1.5"
    EMBED_DIM: int = 384

    # --- limits ---
    MAX_UPLOAD_MB: int = 15
    MAX_PDF_PAGES: int = 150

    # --- tunable thresholds ---
    SILENCE_END_MS: int = 1300
    MIN_SPEECH_MS: int = 400
    BARGE_IN_MIN_MS: int = 300
    MAX_ANSWER_MS: int = 120000
    NO_SPEECH_PROB_MAX: float = 0.6
    NUDGE_AFTER_MS: int = 45000
    STT_TIMEOUT_S: float = 15
    LLM_TIMEOUT_S: float = 15
    TTS_TIMEOUT_S: float = 10
    GROQ_TPM_BUDGET: int = 7000
    QUESTIONS_MIN: int = 2
    QUESTIONS_MAX: int = 4

    # --- chunking ---
    CHUNK_CHARS: int = 1500
    CHUNK_OVERLAP: int = 200
    CHUNK_MIN_CHARS: int = 200

    @property
    def origins(self) -> list[str]:
        return [o.strip().rstrip("/") for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
