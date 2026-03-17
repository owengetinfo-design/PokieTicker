from pydantic_settings import BaseSettings
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    polygon_api_key: str = ""
    anthropic_api_key: str = ""
    tushare_api_key: str = ""  # For A-share and HK stock data
    database_path: str = str(PROJECT_ROOT / "pokieticker.db")

    # AI Provider settings
    ai_provider: str = "anthropic"  # "anthropic" or "kimi"
    kimi_api_key: str = ""  # Moonshot Kimi API key

    model_config = {"env_file": str(PROJECT_ROOT / ".env"), "env_file_encoding": "utf-8"}


settings = Settings()
