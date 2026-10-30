"""Server-only model settings. Public diagnostics never expose credentials."""
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCAL_SETTINGS = ROOT / ".local" / "settings.json"
LOCAL_NAMES = {"GEMINI_API_KEY", "GEMINI_MODEL", "AI_PROVIDER"}
DEFAULT_GEMINI_MODEL = "gemini-flash-latest"


@dataclass(frozen=True)
class Settings:
    backend: str
    model: str
    api_key: str = field(repr=False)
    base_url: str = ""
    credential_source: str = "missing"
    error: str | None = None

    @property
    def configured(self) -> bool:
        return bool(self.api_key and self.model and not self.error)


def get_settings() -> Settings:
    local = {}
    error = None
    if LOCAL_SETTINGS.exists():
        try:
            if LOCAL_SETTINGS.stat().st_size > 16384:
                raise ValueError("size")
            raw = json.loads(LOCAL_SETTINGS.read_text(encoding="utf-8"))
            if not isinstance(raw, dict) or any(not isinstance(raw.get(k, ""), str) for k in LOCAL_NAMES):
                raise ValueError("shape")
            local = {k: v for k, v in raw.items() if k in LOCAL_NAMES}
        except (OSError, ValueError, TypeError):
            error = "Tệp cấu hình Gemini cục bộ không hợp lệ; chạy lại run.py --configure-gemini."

    def value(name: str, default: str = "") -> str:
        # A deliberately empty environment value also overrides saved local values.
        return os.environ[name].strip() if name in os.environ else local.get(name, default).strip()

    configured_backend = value("AI_PROVIDER")
    backend = configured_backend or ("gemini" if value("GEMINI_API_KEY") else "openai" if value("AI_API_KEY") else "gemini")
    if backend not in {"gemini", "openai"}:
        error = "AI_PROVIDER phải là gemini hoặc openai."
    key_name = "AI_API_KEY" if backend == "openai" else "GEMINI_API_KEY"
    api_key = value(key_name)
    model = value("AI_MODEL") if backend == "openai" else value("GEMINI_MODEL", DEFAULT_GEMINI_MODEL)
    if backend == "gemini":
        model = model.removeprefix("models/")
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,119}", model):
            error = "GEMINI_MODEL phải là model ID hợp lệ, không phải URL; kiểm tra model trong Google AI Studio."
    source = "environment" if key_name in os.environ and api_key else "local" if api_key else "missing"
    return Settings(backend=backend, model=model, api_key=api_key,
                    base_url=value("AI_BASE_URL", "https://api.openai.com/v1").rstrip("/") if backend == "openai" else "https://generativelanguage.googleapis.com/v1beta",
                    credential_source=source, error=error)


def public_settings() -> dict:
    settings = get_settings()
    result = {"backend": settings.backend, "model": settings.model,
              "configured": settings.configured, "credential_source": settings.credential_source}
    if settings.error:
        result["error"] = settings.error
    return result
