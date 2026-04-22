from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://chores:chores@db/chores"
    jwt_secret: str = "your-secret-key-change-in-production"  # Should be in .env

    model_config = {"env_file": ".env"}


settings = Settings()
