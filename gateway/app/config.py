import os


class Settings:
    # --- Auth ---
    JWT_SECRET = os.getenv("JWT_SECRET", "change-me-in-production-please")
    JWT_ALG = "HS256"
    ACCESS_TTL = int(os.getenv("ACCESS_TTL", "900"))          # 15 min
    REFRESH_TTL = int(os.getenv("REFRESH_TTL", "2592000"))    # 30 days

    # --- Redis (sessions) ---
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    # --- Browser host control API ---
    BROWSER_HOST_URL = os.getenv("BROWSER_HOST_URL", "http://localhost:9000")

    # --- Logging sink (ClickHouse HTTP) ---
    CLICKHOUSE_URL = os.getenv("CLICKHOUSE_URL", "http://localhost:8123")
    CLICKHOUSE_DB = os.getenv("CLICKHOUSE_DB", "rbi")

    # --- Demo user store (replace with real IdP/DB in prod) ---
    # username -> bcrypt-able plaintext for demo only
    DEMO_USERS = {
        "admin": os.getenv("ADMIN_PASSWORD", "admin123"),
    }

    COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false").lower() == "true"


settings = Settings()
