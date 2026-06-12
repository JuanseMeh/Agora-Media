from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    # Google Cloud
    google_application_credentials: str | None = Field(
        validation_alias="GOOGLE_APPLICATION_CREDENTIALS", default=None
    )
    gcs_bucket_name: str = Field(
        validation_alias="GCS_BUCKET_NAME", default="agora-media-uploads"
    )
    gcs_location: str = Field(validation_alias="GCS_LOCATION", default="US")

    # Services (Docker internal DNS)
    users_service_url: str = Field(
        validation_alias="USERS_SERVICE_URL", default="http://user-service:8080"
    )
    workspace_service_url: str = Field(
        validation_alias="WORKSPACE_SERVICE_URL",
        default="http://workspace-service:8080",
    )

    # PostgreSQL
    database_url: str = Field(validation_alias="DATABASE_URL")

    # App
    app_port: int = Field(validation_alias="APP_PORT", default=8003)
    app_env: str = Field(validation_alias="APP_ENV", default="development")
    log_level: str = Field(validation_alias="LOG_LEVEL", default="INFO")

    # Signed URLs
    signed_url_expiry_seconds: int = Field(
        validation_alias="SIGNED_URL_EXPIRY_SECONDS", default=3600
    )

    # Processing
    max_file_size_mb: int = Field(validation_alias="MAX_FILE_SIZE_MB", default=100)
    ocr_language_hints: str = Field(
        validation_alias="OCR_LANGUAGE_HINTS", default="es,en"
    )


settings = Settings()
