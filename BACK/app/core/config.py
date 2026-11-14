"""Configuración leída de variables de entorno / BACK/.env."""
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

BACK_DIR = Path(__file__).resolve().parents[2]
REPO_DIR = BACK_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACK_DIR / ".env", extra="ignore")

    # ── Fuente de datos ───────────────────────────────
    data_source: Literal["supabase", "mock"] = "mock"

    # ── Supabase ──────────────────────────────────────
    supabase_url: str = ""
    supabase_anon_key: str = ""     # publishable (sb_publishable_…) o anon JWT: lecturas + validar login
    supabase_secret_key: str = ""   # sb_secret_… : SOLO servidor; respaldo de lectura si no hay anon

    # ── Seguridad ─────────────────────────────────────
    admin_api_key: str = ""
    admin_emails: str = ""

    # ── API ───────────────────────────────────────────
    cors_origins: str = "http://localhost:3000"
    cache_ttl_seconds: int = 3600
    default_crop: str = "cacao"

    # ── Modelo ML (dentro del backend) ────────────────
    predictor_mode: Literal["local", "off"] = "local"
    model_path: str = "models/cacao_loss.joblib"
    ml_inference_module: str = "ml.inference"   # módulo opcional de ML (ml/ en la raíz del repo)

    # ── IA (insights y recomendaciones) ───────────────
    ai_provider: Literal["deepseek", "anthropic"] = "deepseek"
    ai_model: str = ""                       # vacío = el de defecto del proveedor
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    anthropic_api_key: str = ""
    ai_effort: Literal["low", "medium", "high", "xhigh", "max"] = "medium"   # solo anthropic
    ai_cache_ttl_seconds: int = 6 * 3600

    # ── Fuentes externas sin key ──────────────────────
    nasa_power_url: str = "https://power.larc.nasa.gov/api"
    noaa_oni_url: str = "https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt"
    noaa_sst_url: str = "https://www.cpc.ncep.noaa.gov/data/indices/sstoi.indices"

    @property
    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def admin_email_set(self) -> set[str]:
        return {e.strip().lower() for e in self.admin_emails.split(",") if e.strip()}

    @property
    def ai_model_name(self) -> str:
        return self.ai_model or {"deepseek": "deepseek-chat", "anthropic": "claude-opus-5-5"}[self.ai_provider]

    @property
    def model_file(self) -> Path:
        p = Path(self.model_path)
        return p if p.is_absolute() else BACK_DIR / p


@lru_cache
def get_settings() -> Settings:
    return Settings()
