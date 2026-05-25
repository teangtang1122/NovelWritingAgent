"""Model selection for project cataloging."""
from __future__ import annotations

from ...database.models import APIConfig
from ...database.session import SessionLocal
from .constants import CHEAP_MODEL_BY_PROVIDER


def default_cataloging_model(model_override: str | None = None) -> str | None:
    if model_override:
        return model_override
    db = SessionLocal()
    try:
        config = db.query(APIConfig).filter(APIConfig.is_global_default == True).first()
        if not config:
            return None
        model = CHEAP_MODEL_BY_PROVIDER.get(config.provider, config.default_model)
        return f"{config.provider}:{model}"
    finally:
        db.close()


def cataloging_extra_body(model: str | None) -> dict | None:
    provider = (model or "").split(":", 1)[0].lower()
    if provider == "deepseek":
        return {"thinking": {"type": "disabled"}}
    return None
