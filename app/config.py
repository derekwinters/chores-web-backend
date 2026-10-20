from pydantic_settings import BaseSettings

# Current application version
APP_VERSION = "2.6.0"  # x-release-please-version

# Current API major version. The versioned API surface is mounted under
# `/v1` (see V1_PREFIX in app/main.py); this is the corresponding negotiable
# identifier exposed on the unversioned /status/ endpoint.
API_VERSION = "v1"

# All API major versions this backend currently serves. Exposed on /status/
# so a client can enumerate and negotiate deliberately (issue #16). Add the
# next identifier here when a new major version is mounted alongside v1.
SUPPORTED_API_VERSIONS = ["v1"]


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://chores:chores@db/chores"
    jwt_secret: str  # Required — no default. Set JWT_SECRET in environment or .env file.

    model_config = {"env_file": ".env"}


settings = Settings()
