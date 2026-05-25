from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = Field(default="InfoEdge API")
    env: str = Field(default="development")
    debug: bool = Field(default=True)

    pg_user: str = "postgres"
    pg_password: str = "postgres"
    pg_host: str = "localhost"
    pg_port: int = 5432
    pg_db: str = "postgres"

    redis_host: str = "localhost"
    redis_port: int = 6370
    redis_db: int = 0
    redis_password: str = ""

    apify_token: str = ""
    apify_run_timeout_seconds: int = 180
    pipeline_limit_per_source: int = 8
    opportunity_min_score: int = 66
    glm_api_key: str = ""
    glm_base_url: str = "https://open.bigmodel.cn/api/paas/v4"
    glm_model: str = "glm-5.1"
    glm_timeout_seconds: int = 45

    model_config = SettingsConfigDict(
        env_prefix="",
        env_file=".env",
        env_file_encoding="utf-8",
    )

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.pg_user}:{self.pg_password}@"
            f"{self.pg_host}:{self.pg_port}/{self.pg_db}"
        )

    @property
    def redis_url(self) -> str:
        return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/{self.redis_db}"


settings = Settings()
