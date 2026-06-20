import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


db_url = os.environ.get("DATABASE_URL")
if db_url and db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)


class Config:
    """Base configuration."""
    SECRET_KEY = os.environ.get("SECRET_KEY", "mini-erp-dev-secret-key-change-in-prod")
    SQLALCHEMY_DATABASE_URI = db_url or (
        "sqlite:///" + os.path.join(BASE_DIR, "database", "mini_erp.db")
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    PERMANENT_SESSION_LIFETIME = 3600  # 1 hour
    # Cross-origin cookie settings (needed for Vercel frontend + Render backend)
    SESSION_COOKIE_SAMESITE = "None"
    SESSION_COOKIE_SECURE = True


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_SAMESITE = "None"


config_by_name = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
}
