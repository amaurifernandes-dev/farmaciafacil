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

    # Onde o sistema está instalado. "nuvem": servidor na internet, várias farmácias no mesmo banco.
    # "farmacia": instalado num computador da própria farmácia, com o banco dela (on-premise).
    instalacao: Literal["nuvem", "farmacia"] = "nuvem"

    # NFC-e. "desligado" não emite; "falso" simula a SEFAZ (desenvolvimento e testes).
    nfce_provedor: Literal["desligado", "falso", "focus"] = "desligado"
    # Tokens da Focus NFe, um por ambiente. O certificado A1 e o CSC ficam no painel da Focus.
    focus_nfe_token_homologacao: str = ""
    focus_nfe_token_producao: str = ""

    # Assistente de IA (Claude, da Anthropic). Sem a chave, o assistente fica desligado.
    anthropic_api_key: str = ""
    assistente_modelo: str = "claude-opus-5-5"

    @property
    def loja_online_disponivel(self) -> bool:
        """A loja online e o Pix pelo site precisam do sistema na internet; instalado na farmácia, ficam fora."""
        return self.instalacao == "nuvem"

    @field_validator("database_url", "migration_database_url")
    @classmethod
    def _driver(cls, valor: str) -> str:
        return _usar_psycopg(valor)


@lru_cache
def get_settings() -> Settings:
    return Settings()
