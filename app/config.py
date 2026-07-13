from pydantic_settings import BaseSettings

# Current application version
APP_VERSION = "2.3.0"  # x-release-please-version


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://chores:chores@db/chores"
    jwt_secret: str  # Required — no default. Set JWT_SECRET in environment or .env file.

    model_config = {"env_file": ".env"}


settings = Settings()
