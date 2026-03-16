from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional

from backend.config import settings

router = APIRouter()


class SettingsUpdate(BaseModel):
    anthropicApiKey: Optional[str] = None
    polygonApiKey: Optional[str] = None
    layer1Model: Optional[str] = None
    layer1BatchSize: Optional[int] = None
    layer1MaxTokens: Optional[int] = None
    layer2Model: Optional[str] = None
    layer2MaxTokens: Optional[int] = None
    forecastWindow: Optional[int] = None
    similarPeriodsTopK: Optional[int] = None
    similarArticlesTopK: Optional[int] = None


# Runtime overrides (not persisted to .env)
_runtime: dict = {}


def get_setting(key: str, default=None):
    """Get a runtime setting, falling back to config.py settings or default."""
    return _runtime.get(key, default)


@router.get("")
def get_settings():
    """Return current configuration (API keys masked)."""
    anthropic_key = _runtime.get("anthropicApiKey", settings.anthropic_api_key)
    polygon_key = _runtime.get("polygonApiKey", settings.polygon_api_key)
    return {
        "anthropicApiKey": f"...{anthropic_key[-4:]}" if len(anthropic_key) > 4 else "",
        "polygonApiKey": f"...{polygon_key[-4:]}" if len(polygon_key) > 4 else "",
        "layer1Model": _runtime.get("layer1Model", "claude-haiku-4-5-20251001"),
        "layer1BatchSize": _runtime.get("layer1BatchSize", 50),
        "layer1MaxTokens": _runtime.get("layer1MaxTokens", 4096),
        "layer2Model": _runtime.get("layer2Model", "claude-sonnet-4-5-20250929"),
        "layer2MaxTokens": _runtime.get("layer2MaxTokens", 1024),
        "forecastWindow": _runtime.get("forecastWindow", 7),
        "similarPeriodsTopK": _runtime.get("similarPeriodsTopK", 10),
        "similarArticlesTopK": _runtime.get("similarArticlesTopK", 20),
    }


@router.post("")
def update_settings(body: SettingsUpdate):
    """Update runtime configuration."""
    updates = body.model_dump(exclude_none=True)

    # Update API keys in the actual settings object too
    if "anthropicApiKey" in updates and updates["anthropicApiKey"]:
        settings.anthropic_api_key = updates["anthropicApiKey"]
    if "polygonApiKey" in updates and updates["polygonApiKey"]:
        settings.polygon_api_key = updates["polygonApiKey"]

    _runtime.update(updates)
    return {"status": "ok", "updated": list(updates.keys())}
