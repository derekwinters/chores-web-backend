from pydantic_settings import BaseSettings

# Current application version
APP_VERSION = "1.5.1"  # x-release-please-version


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://chores:chores@db/chores"
    jwt_secret: str = "your-secret-key-change-in-production"  # Should be in .env

    model_config = {"env_file": ".env"}


settings = Settings()
