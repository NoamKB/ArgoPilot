from pathlib import Path

from pydantic import Field, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

SERVICE_DIR = Path(__file__).resolve().parent
ENV_FILE = SERVICE_DIR / ".env"


class Settings(BaseSettings):
    """planner-service settings. An environment variable wins over .env. Every field is required."""

    # extra="ignore": .env may hold variables this class does not define.
    model_config = SettingsConfigDict(env_file=ENV_FILE, extra="ignore")

    registry_url: str
    weather_url: str
    registry_timeout_seconds: float = Field(gt=0)
    weather_timeout_seconds: float = Field(gt=0)


def load_settings() -> Settings:
    """Read the settings, or stop with a message that names each bad variable.

    pydantic's own message is not used: for a missing variable it prints every other value it read.
    """
    try:
        return Settings()
    except ValidationError as exc:
        problems = []
        for error in exc.errors():
            name = "_".join(str(part) for part in error["loc"]).upper() or "settings"
            problems.append(f"{name}: {error['msg']}")
        raise RuntimeError("Invalid planner-service configuration (see .env.example): " + "; ".join(problems)) from None
