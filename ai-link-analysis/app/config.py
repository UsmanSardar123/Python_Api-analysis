"""Configuration management for the AI-Powered Website Link Analysis API."""

import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Load .env file from project root or current working directory if present
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_PROJECT_ROOT / ".env", override=False)
load_dotenv(override=False)


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=(".env", str(_PROJECT_ROOT / ".env")),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Application Info
    app_name: str = Field(
        default="AI-Powered Website Link Analysis API",
        description="Public name of the FastAPI service.",
    )
    app_version: str = Field(default="1.0.0", description="API semantic version.")
    app_env: str = Field(default="development", validation_alias="APP_ENV")
    host: str = Field(default="0.0.0.0", validation_alias="HOST")
    port: int = Field(default=8000, validation_alias="PORT")
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")

    # LLM Provider Configuration
    llm_provider: Literal["gemini", "openai"] = Field(
        default="gemini",
        validation_alias="LLM_PROVIDER",
        description="Primary LLM provider to use ('gemini' or 'openai').",
    )
    gemini_api_key: str = Field(
        default="",
        validation_alias="GEMINI_API_KEY",
        description="Google Gemini API key.",
    )
    gemini_model: str = Field(
        default="gemini-2.5-flash",
        validation_alias="GEMINI_MODEL",
        description="Default Google Gemini model identifier.",
    )
    openai_api_key: str = Field(
        default="",
        validation_alias="OPENAI_API_KEY",
        description="OpenAI API key.",
    )
    openai_model: str = Field(
        default="gpt-4o-mini",
        validation_alias="OPENAI_MODEL",
        description="Default OpenAI model identifier.",
    )
    enable_llm_fallback: bool = Field(
        default=True,
        validation_alias="ENABLE_LLM_FALLBACK",
        description="Whether to automatically try the secondary LLM provider if the primary fails.",
    )
    enable_demo_mode_without_api_key: bool = Field(
        default=False,
        validation_alias="ENABLE_DEMO_MODE_WITHOUT_API_KEY",
        description=(
            "When true and no LLM API keys are configured, generates a deterministic "
            "rule-based structured analysis from extracted website facts for local testing."
        ),
    )

    # Website Extraction & Security Limits
    http_timeout_seconds: float = Field(
        default=15.0,
        validation_alias="HTTP_TIMEOUT_SECONDS",
        ge=1.0,
        le=60.0,
        description="Maximum timeout in seconds for HTTP requests.",
    )
    max_response_bytes: int = Field(
        default=2_097_152,  # 2 MB
        validation_alias="MAX_RESPONSE_BYTES",
        ge=65_536,
        le=10_485_760,
        description="Maximum allowed HTTP response body size in bytes.",
    )
    max_redirects: int = Field(
        default=5,
        validation_alias="MAX_REDIRECTS",
        ge=0,
        le=10,
        description="Maximum number of safe redirects to follow.",
    )
    user_agent: str = Field(
        default="AILinkAnalysisBot/1.0 (+https://github.com/example/ai-link-analysis)",
        validation_alias="USER_AGENT",
        description="HTTP User-Agent header sent during website extraction.",
    )

    def has_valid_gemini_key(self) -> bool:
        """Check whether a non-placeholder Gemini API key is configured."""
        key = (self.gemini_api_key or os.getenv("GEMINI_API_KEY", "")).strip()
        return bool(key) and key not in {
            "your_gemini_api_key_here",
            "YOUR_GEMINI_API_KEY",
            "changeme",
        }

    def has_valid_openai_key(self) -> bool:
        """Check whether a non-placeholder OpenAI API key is configured."""
        key = (self.openai_api_key or os.getenv("OPENAI_API_KEY", "")).strip()
        return bool(key) and key not in {
            "your_openai_api_key_here",
            "YOUR_OPENAI_API_KEY",
            "changeme",
        }


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings instance."""
    return Settings()
