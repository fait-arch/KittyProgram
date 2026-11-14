"""Configuración: lee BACK/.env y la valida (pydantic-settings).

Prueba:  python -m app.core.config
"""
from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACK_DIR = Path(__file__).resolve().parents[2]
ENV_FILE = BACK_DIR / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE, env_file_encoding="utf-8", extra="ignore")

    # App
    APP_ENV: str = "development"
    CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"

    # 1. Google Earth Engine
    GEE_PROJECT: str = ""
    GEE_SERVICE_ACCOUNT: str = ""
    GEE_PRIVATE_KEY_PATH: str = ""
    GEE_PRIVATE_KEY_JSON: str = ""

    # 2. Supabase
    SUPABASE_URL: str = ""
    SUPABASE_ANON_KEY: str = ""
    SUPABASE_SERVICE_ROLE_KEY: str = ""
    ADMIN_EMAILS: str = ""

    # 3. Earthdata (AppEEARS / ECOSTRESS)
    EARTHDATA_USER: str = ""
    EARTHDATA_PASS: str = ""
    EARTHDATA_TOKEN: str = ""

    # 4. Fuentes sin cuenta
    NOAA_ONI_URL: str = "https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt"
    NOAA_SSTOI_URL: str = "https://www.cpc.ncep.noaa.gov/data/indices/sstoi.indices"
    ECOCROP_CSV_URL: str = "https://raw.githubusercontent.com/OpenCLIM/ecocrop/main/EcoCrop_DB.csv"
    FAOSTAT_BULK_URL: str = (
        "https://bulks-faostat.fao.org/production/Production_Crops_Livestock_E_Americas.zip"
    )
    NASA_POWER_URL: str = "https://power.larc.nasa.gov/api/temporal"
    GBIF_API_URL: str = "https://api.gbif.org/v1"
    APPEEARS_API_URL: str = "https://appeears.earthdatacloud.nasa.gov/api"

    # 5. Proyecto
    CROP_SCIENTIFIC_NAME: str = "Theobroma cacao"
    FAOSTAT_ITEM: str = "Cocoa beans"
    PROVINCES: str = "Los Rios,Guayas,Manabi,Esmeraldas,El Oro"
    POWER_START_YEAR: int = 2005
    POWER_END_YEAR: int = 2024

    # 6. Caché
    CACHE_DIR: str = "./cache"
    CACHE_TTL_HOURS: int = 168
    HTTP_TIMEOUT_SECONDS: int = 60

    @field_validator("GEE_PROJECT")
    @classmethod
    def _gee_not_api_key(cls, v: str) -> str:
        if v.startswith("AIza"):
            raise ValueError("GEE_PROJECT es el ID del proyecto (ej. 'mi-proyecto-123'), no una API key")
        return v.strip()

    @field_validator("SUPABASE_URL")
    @classmethod
    def _clean_supabase_url(cls, v: str) -> str:
        v = v.strip().rstrip("/")
        return v.removesuffix("/rest/v1")

    # ── Ayudas ──
    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def admin_emails(self) -> list[str]:
        return [e.strip().lower() for e in self.ADMIN_EMAILS.split(",") if e.strip()]

    @property
    def provinces(self) -> list[str]:
        return [p.strip() for p in self.PROVINCES.split(",") if p.strip()]

    @property
    def cache_path(self) -> Path:
        p = Path(self.CACHE_DIR)
        return p if p.is_absolute() else BACK_DIR / p

    @property
    def data_raw_path(self) -> Path:
        return BACK_DIR / "data" / "raw"

    @property
    def gee_configured(self) -> bool:
        return bool(self.GEE_PROJECT) and self.GEE_PROJECT != "tu-project-id"

    @property
    def gee_uses_service_account(self) -> bool:
        return bool(self.GEE_SERVICE_ACCOUNT and (self.GEE_PRIVATE_KEY_PATH or self.GEE_PRIVATE_KEY_JSON))

    @property
    def earthdata_configured(self) -> bool:
        return bool(self.EARTHDATA_USER and self.EARTHDATA_PASS)

    def missing_required(self) -> list[str]:
        faltan = []
        if not self.gee_configured:
            faltan.append("GEE_PROJECT")
        if not self.SUPABASE_URL or "<ref>" in self.SUPABASE_URL:
            faltan.append("SUPABASE_URL")
        if not self.SUPABASE_ANON_KEY:
            faltan.append("SUPABASE_ANON_KEY")
        if not self.SUPABASE_SERVICE_ROLE_KEY:
            faltan.append("SUPABASE_SERVICE_ROLE_KEY")
        return faltan


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()


if __name__ == "__main__":
    s = settings
    print("Archivo .env:", ENV_FILE, "(existe)" if ENV_FILE.exists() else "(NO EXISTE)")
    print("GEE_PROJECT:", s.GEE_PROJECT or "—", "| service account:", s.gee_uses_service_account)
    print("SUPABASE_URL:", s.SUPABASE_URL or "—")
    print("Anon key:", bool(s.SUPABASE_ANON_KEY), "| Service role:", bool(s.SUPABASE_SERVICE_ROLE_KEY))
    print("Earthdata (Fase 3):", s.earthdata_configured)
    print("Cultivo:", s.CROP_SCIENTIFIC_NAME, "| Provincias:", ", ".join(s.provinces))
    faltan = s.missing_required()
    print("\n✅ Todo listo" if not faltan else f"\n⚠️  Faltan: {', '.join(faltan)}")
