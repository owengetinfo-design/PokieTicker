from pydantic_settings import BaseSettings
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    polygon_api_key: str = ""
    anthropic_api_key: str = ""
    database_path: str = str(PROJECT_ROOT / "pokieticker.db")

    layer1_model: str = "claude-haiku-4-5-20251001"
    layer1_batch_size: int = 50
    layer1_max_tokens: int = 4096
    layer2_model: str = "claude-sonnet-4-5-20250929"
    layer2_max_tokens: int = 1024
    forecast_window: int = 7
    similar_periods_top_k: int = 10
    similar_articles_top_k: int = 20

    model_config = {"env_file": str(PROJECT_ROOT / ".env"), "env_file_encoding": "utf-8"}


settings = Settings()
