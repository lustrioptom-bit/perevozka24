from pydantic_settings import BaseSettings


def _db_host(url: str) -> str:
    try:
        rest = url.split("@", 1)[1]
        return rest.split("/", 1)[0].split(":", 1)[0].split("?")[0].lower()
    except IndexError:
        return ""


class Settings(BaseSettings):
    BOT_TOKEN: str = ""
    ADMIN_IDS_RAW: str = ""
    CHANNEL_ID: str = ""
    CHANNEL_USERNAME: str = "perevozkauakh"
    DATABASE_URL: str = "postgresql+asyncpg://postgres:password@localhost:5432/perevozka"
    WEBAPP_SECRET_KEY: str = "change_me"
    WEBAPP_HOST: str = "0.0.0.0"
    WEBAPP_PORT: int = 8000
    PUBLIC_URL: str = ""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @property
    def CHANNEL_LINK(self) -> str:
        username = self.CHANNEL_USERNAME.strip().lstrip("@")
        if username:
            return f"https://t.me/{username}"
        return self.CHANNEL_ID

    @property
    def ADMIN_IDS(self) -> list[int]:
        if not self.ADMIN_IDS_RAW:
            return []
        return [int(x.strip()) for x in self.ADMIN_IDS_RAW.split(",") if x.strip()]

    @property
    def DATABASE_URL_ASYNC(self) -> str:
        """URL for SQLAlchemy + asyncpg (Neon/Supabase/Render compatible, adds ssl=require)."""
        url = self.DATABASE_URL.strip()
        if not url:
            return url
        if url.startswith("postgres://"):
            url = "postgresql://" + url[len("postgres://"):]
        if url.startswith("postgresql+psycopg://") or url.startswith("postgresql+psycopg2://"):
            url = "postgresql://" + url.split("://", 1)[1]
        if url.startswith("postgresql://"):
            url = "postgresql+asyncpg://" + url[len("postgresql://"):]
        host = _db_host(url)
        if host and host not in ("localhost", "127.0.0.1", "::1"):
            if "sslmode=" in url:
                url = url.replace("sslmode=", "ssl=")
            elif "ssl=" not in url:
                sep = "&" if "?" in url else "?"
                url += f"{sep}ssl=require"
        return url

    @property
    def DATABASE_URL_SYNC(self) -> str:
        """URL for psycopg2 / libpq (plain postgresql:// with sslmode=require)."""
        url = self.DATABASE_URL.strip()
        if not url:
            return url
        if url.startswith("postgres://"):
            url = "postgresql://" + url[len("postgres://"):]
        for prefix in ("postgresql+asyncpg://", "postgresql+psycopg://", "postgresql+psycopg2://"):
            if url.startswith(prefix):
                url = "postgresql://" + url[len(prefix):]
                break
        host = _db_host(url)
        if host and host not in ("localhost", "127.0.0.1", "::1"):
            if "ssl=" in url and "sslmode=" not in url:
                url = url.replace("ssl=", "sslmode=", 1)
            elif "sslmode=" not in url and "ssl=" not in url:
                sep = "&" if "?" in url else "?"
                url += f"{sep}sslmode=require"
        return url

    @property
    def WEBAPP_BASE_URL(self) -> str:
        if self.PUBLIC_URL:
            return self.PUBLIC_URL.rstrip("/") + "/app"
        return f"http://{self.WEBAPP_HOST}:{self.WEBAPP_PORT}/app"


settings = Settings()
