"""Application configuration with environment variables."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_env: Literal["development", "production"] = Field(default="development")
    app_log_level: str = Field(default="INFO")
    app_max_upload_size_mb: int = Field(default=20)
    app_allowed_extensions: str = Field(default=".pdf,.png,.jpg,.jpeg,.tiff,.bmp")

    # Huawei Cloud ModelArts MaaS
    maas_api_key: str = Field(default="")
    maas_region: str = Field(default="cn-north-4")
    maas_endpoint: str = Field(default="https://api-cn-north-4.modelarts-maas.com")
    maas_model_reasoner: str = Field(default="deepseek-r1")
    maas_model_writer: str = Field(default="qwen-plus")

    # Huawei Cloud OCR
    ocr_endpoint: str = Field(default="")
    ocr_region: str = Field(default="cn-north-4")
    ocr_ak: str = Field(default="")
    ocr_sk: str = Field(default="")
    ocr_project_id: str = Field(default="")

    # Rate limiting
    max_requests_per_minute: int = Field(default=60)

    # Security
    enable_redaction: bool = Field(default=True)

    # Disclaimer text
    @property
    def disclaimer(self) -> str:
        return (
            "⚠️ ADVISORY ONLY - This system provides decision support and does NOT make "
            "final legal determinations. All risk scores and recommendations must be "
            "reviewed by qualified customs officials. The authority assumes full "
            "responsibility for all final decisions."
        )

    # Derived properties
    @property
    def maas_chat_url(self) -> str:
        return f"{self.maas_endpoint}/v2/chat/completions"

    @property
    def allowed_extensions_set(self) -> set[str]:
        return set(ext.strip() for ext in self.app_allowed_extensions.split(","))

    @property
    def max_upload_bytes(self) -> int:
        return self.app_max_upload_size_mb * 1024 * 1024

    @field_validator("app_log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        valid = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if v.upper() not in valid:
            raise ValueError(f"log_level must be one of {valid}")
        return v.upper()


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Global settings instance
settings = get_settings()
