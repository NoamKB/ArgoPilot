from pathlib import Path

from pydantic import Field, SecretStr, ValidationError, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

SERVICE_DIR = Path(__file__).resolve().parent
ENV_FILE = SERVICE_DIR / ".env"


class Settings(BaseSettings):
    """weather-service settings. An environment variable wins over .env. Every field except the API key is required."""

    # extra="ignore": .env may hold variables this class does not define.
    model_config = SettingsConfigDict(env_file=ENV_FILE, extra="ignore")

    provider_base_url: str
    # Empty on Open-Meteo's free tier. SecretStr keeps the key out of logs and error messages.
    provider_api_key: SecretStr = SecretStr("")
    provider_timeout_seconds: float = Field(gt=0)
    provider_retries: int = Field(ge=0)
    forecast_fresh_hours: float = Field(gt=0)
    forecast_max_stale_hours: float = Field(gt=0)

    @model_validator(mode="after")
    def stale_limit_is_not_shorter_than_freshness(self) -> "Settings":
        if self.forecast_max_stale_hours < self.forecast_fresh_hours:
            raise ValueError("FORECAST_MAX_STALE_HOURS must not be less than FORECAST_FRESH_HOURS")
        return self


def load_settings() -> Settings:
    """Read the settings, or stop with a message that names each bad variable.

    pydantic's own message is not used: for a missing variable it prints every other value it read, API key included.
    """
    try:
        return Settings()
    except ValidationError as exc:
        problems = []
        for error in exc.errors():
            name = "_".join(str(part) for part in error["loc"]).upper() or "settings"
            problems.append(f"{name}: {error['msg']}")
        raise RuntimeError("Invalid weather-service configuration (see .env.example): " + "; ".join(problems)) from None
