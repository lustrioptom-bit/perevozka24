from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    BOT_TOKEN: str = ""
    ADMIN_IDS_RAW: str = ""
    CHANNEL_ID: str = ""
    DATABASE_URL: str = "postgresql+asyncpg://postgres:password@localhost:5432/perevozka"
    WEBAPP_SECRET_KEY: str = "change_me"
    WEBAPP_HOST: str = "0.0.0.0"
    WEBAPP_PORT: int = 8000
    PUBLIC_URL: str = ""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @property
    def ADMIN_IDS(self) -> list[int]:
        if not self.ADMIN_IDS_RAW:
            return []
        return [int(x.strip()) for x in self.ADMIN_IDS_RAW.split(",") if x.strip()]

    @property
    def WEBAPP_BASE_URL(self) -> str:
        if self.PUBLIC_URL:
            return self.PUBLIC_URL.rstrip("/")
        return f"http://{self.WEBAPP_HOST}:{self.WEBAPP_PORT}"


settings = Settings()
