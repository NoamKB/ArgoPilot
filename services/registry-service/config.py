from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

SERVICE_DIR = Path(__file__).resolve().parent
ENV_FILE = SERVICE_DIR / ".env"
DEFAULT_DATABASE_URL = f"sqlite:///{SERVICE_DIR / 'registry.db'}"


class Settings(BaseSettings):
    """registry-service settings. An environment variable wins over .env, and .env over the default."""

    # extra="ignore": .env may hold variables this class does not define.
    model_config = SettingsConfigDict(env_file=ENV_FILE, extra="ignore")

    # A plain str, not validated here: a pydantic error would print the value, password included.
    # db.parse_database_url checks it with a fixed error message.
    database_url: str = DEFAULT_DATABASE_URL

    @field_validator("database_url")
    @classmethod
    def empty_means_default(cls, value: str) -> str:
        # An empty value, even one exported in the environment, means the default SQLite file (JL-010).
        return value or DEFAULT_DATABASE_URL
