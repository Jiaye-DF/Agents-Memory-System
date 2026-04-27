from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_LOCALHOST_HOSTS = ("localhost", "127.0.0.1", "0.0.0.0")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )

    APP_ENV: str = "development"

    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str

    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0

    SECRET_KEY: str
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    @field_validator("SECRET_KEY")
    @classmethod
    def _validate_secret_key(cls, v: str) -> str:
        if len(v) < 32:
            raise ValueError(
                "SECRET_KEY 長度不可低於 32 字元（建議 64 字元亂數）"
            )
        return v

    @model_validator(mode="after")
    def _validate_cors_for_production(self) -> "Settings":
        if self.APP_ENV != "production":
            return self
        for origin in self.CORS_ORIGINS:
            if origin == "*":
                raise ValueError(
                    "APP_ENV=production 下 CORS_ORIGINS 禁止使用 '*'"
                )
            host = origin.split("//", 1)[-1].split(":", 1)[0].lower()
            if host in _LOCALHOST_HOSTS:
                raise ValueError(
                    f"APP_ENV=production 下 CORS_ORIGINS 禁止包含本機 origin：{origin}"
                )
        return self

    SKILLS_UPLOAD_DIR: str = "data/skills"
    SKILLS_MAX_FILE_SIZE: int = 50 * 1024 * 1024

    ATTACHMENTS_UPLOAD_DIR: str = "data/attachments"

    OPENROUTER_API_KEY: str = ""
    OPENROUTER_HTTP_REFERER: str = "http://localhost:3000"
    OPENROUTER_APP_TITLE: str = "Agents Memory System"

    # v1.3.0：LLM 成本 metrics — counterfactual baseline 用的 expensive 模型 id
    # 用於 llm_metering wrapper 計算 baseline_cost_usd（假設全走此模型會花多少）
    LLM_BASELINE_EXPENSIVE_MODEL: str = "anthropic/claude-sonnet-4-6"

    LINE_CHANNEL_ACCESS_TOKEN: str = ""
    LINE_CHANNEL_SECRET: str = ""

    TELEGRAM_BOT_TOKEN: str = ""

    @property
    def DATABASE_URL(self) -> str:
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )


settings = Settings()  # type: ignore[call-arg]
