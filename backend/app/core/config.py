from functools import lru_cache
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _usar_psycopg(url: str) -> str:
    """Aceita a URL como o Neon/Supabase entregam e aponta para o driver psycopg 3."""
    for prefixo in ("postgres://", "postgresql://"):
        if url.startswith(prefixo):
            return "postgresql+psycopg://" + url[len(prefixo):]
    return url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    migration_database_url: str
    app_db_role: str = "ff_app"
    jwt_secret: str
    jwt_expira_horas: int = 12

    # NFC-e. "desligado" não emite; "falso" simula a SEFAZ (desenvolvimento e testes).
    nfce_provedor: Literal["desligado", "falso", "focus"] = "desligado"
    # Tokens da Focus NFe, um por ambiente. O certificado A1 e o CSC ficam no painel da Focus.
    focus_nfe_token_homologacao: str = ""
    focus_nfe_token_producao: str = ""

    @field_validator("database_url", "migration_database_url")
    @classmethod
    def _driver(cls, valor: str) -> str:
        return _usar_psycopg(valor)


@lru_cache
def get_settings() -> Settings:
    return Settings()
