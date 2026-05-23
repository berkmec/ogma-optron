from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/config.py -> repo root is two levels up.
REPO_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = REPO_ROOT / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    hf_token: str = ""
    vision_model: str = "Qwen/Qwen3-VL-30B-A3B-Instruct"
    openai_base_url: str = "https://router.huggingface.co/v1"
    app_host: str = "127.0.0.1"
    app_port: int = 8000
    agent_code_bin: str = ""
    agent_code_api_base_url: str = "https://router.huggingface.co/v1"
    agent_code_api_key: str = ""
    agent_code_model: str = "Qwen/Qwen3-VL-30B-A3B-Instruct"


settings = Settings()
