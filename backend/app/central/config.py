from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.config import _usar_psycopg


class ConfigCentral(BaseSettings):
    """Variáveis com o prefixo CENTRAL_. Nada aqui é compartilhado com o sistema das farmácias."""

    model_config = SettingsConfigDict(env_file=".env", env_prefix="CENTRAL_", extra="ignore")

    database_url: str
    # Chave privada Ed25519 em base64 (gerada com  python -m app.central.gerar_chaves). Nunca vai para o repositório.
    chave_privada: str
    jwt_secret: str
    jwt_expira_horas: int = 8

    @field_validator("database_url")
    @classmethod
    def _driver(cls, valor: str) -> str:
        return _usar_psycopg(valor)


@lru_cache
def get_config() -> ConfigCentral:
    return ConfigCentral()
