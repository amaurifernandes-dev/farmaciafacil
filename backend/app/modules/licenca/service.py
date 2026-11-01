"""A "dll" da licença: confere, sem internet, se este servidor pode funcionar.

Só age com LICENCA_CHAVE_PUBLICA configurada. Sem ela (desenvolvimento e testes), nada é conferido.
"""

import hashlib
import logging
import time
from datetime import UTC, date, datetime, timedelta
from uuid import UUID

import httpx
from fastapi import HTTPException
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.licenca.formato import Licenca, LicencaInvalida, chave_publica, ler, limpar
from app.licenca.situacao import RELOGIO, Situacao, situacao
from app.modules.licenca.models import LicencaInstalada, ServidorLocal
from app.shared.erros import ErroDeNegocio, SemPermissao
from app.shared.modulos import MODULOS

log = logging.getLogger(__name__)

# A resposta 402 diz ao navegador para abrir a tela da licença.
STATUS_BLOQUEIO = 402
_CACHE_SEGUNDOS = 30
_cache: dict[str, tuple[float, Situacao, Licenca | None]] = {}


def exigida() -> bool:
    return bool(get_settings().licenca_chave_publica)


def hoje() -> date:
    return datetime.now(UTC).astimezone().date()


def _servidor(db: Session) -> ServidorLocal:
    servidor = db.get(ServidorLocal, 1)
    if servidor is None:
        db.execute(
            text("INSERT INTO servidor_local (id, maquina_id) VALUES (1, gen_random_uuid()) ON CONFLICT DO NOTHING")
        )
        db.commit()
        servidor = db.get(ServidorLocal, 1)
    return servidor


def codigo_do_servidor(maquina_id: UUID) -> str:
    """16 letras e números que identificam este servidor (o cliente lê para quem vendeu o sistema)."""
    bruto = hashlib.sha256(b"farmaciafacil:" + maquina_id.bytes).hexdigest()[:16].upper()
    return "-".join(bruto[i : i + 4] for i in range(0, 16, 4))


def maquina(db: Session) -> str:
    return codigo_do_servidor(_servidor(db).maquina_id)


def _relogio_voltou(db: Session, dia: date) -> bool:
    """Guarda a maior data já vista. Se a data do computador voltar mais de um dia, desconfia."""
    servidor = _servidor(db)
    if servidor.maior_data is None or dia > servidor.maior_data:
        servidor.maior_data = dia
        db.commit()
        return False
    return dia < servidor.maior_data - timedelta(days=1)


def _ler(codigo: str) -> Licenca:
    return ler(codigo, chave_publica(get_settings().licenca_chave_publica))


def instalada(db: Session, cnpj: str) -> tuple[LicencaInstalada | None, Licenca | None]:
    linha = db.get(LicencaInstalada, cnpj)
    if linha is None:
        return None, None
    try:
        return linha, _ler(linha.codigo)
    except LicencaInvalida:
        return linha, None


def avaliar(db: Session, cnpj: str) -> tuple[Situacao, Licenca | None]:
    _, licenca = instalada(db, cnpj)
    dia = hoje()
    if _relogio_voltou(db, dia):
        return RELOGIO, licenca
    if licenca is not None and licenca.tipo != get_settings().instalacao:
        onde = "o sistema online" if licenca.tipo == "nuvem" else "instalar na farmácia"
        return (
            Situacao(estado="outro_servidor", bloqueia=True, mensagem=f"Esta licença é para {onde}"),
            licenca,
        )
    return situacao(licenca, dia, maquina(db)), licenca


def avaliar_com_cache(db: Session, cnpj: str) -> tuple[Situacao, Licenca | None]:
    agora = time.monotonic()
    guardado = _cache.get(cnpj)
    if guardado and guardado[0] > agora:
        return guardado[1], guardado[2]
    sit, licenca = avaliar(db, cnpj)
    _cache[cnpj] = (agora + _CACHE_SEGUNDOS, sit, licenca)
    return sit, licenca


def esquecer_cache() -> None:
    _cache.clear()


def conferir(db: Session, cnpj: str) -> None:
    """Usado em toda rota com banco: licença encerrada para o sistema."""
    if not exigida():
        return
    sit, _ = avaliar_com_cache(db, cnpj)
    if sit.bloqueia:
        raise HTTPException(STATUS_BLOQUEIO, sit.mensagem)


def bloqueada(db: Session, cnpj: str) -> bool:
    return exigida() and avaliar_com_cache(db, cnpj)[0].bloqueia


def licenca_da(db: Session, cnpj: str) -> Licenca | None:
    if not exigida():
        return None
    return avaliar_com_cache(db, cnpj)[1]


def modulos_fora(db: Session, cnpj: str) -> list[str]:
    """Módulos que a licença não inclui: somem até do Gerenciamento de telas."""
    licenca = licenca_da(db, cnpj)
    if licenca is None or licenca.modulos is None:
        return []
    return [m for m in MODULOS if m not in licenca.modulos]


def conferir_limite(db: Session, farmacia_id, qual: str) -> None:
    """Antes de cadastrar (ou reativar) mais um usuário ou caixa (PDV)."""
    if not exigida():
        return
    from app.modules.auth.models import Usuario
    from app.modules.farmacias.models import Farmacia
    from app.modules.lojas.models import Terminal

    licenca = licenca_da(db, db.get(Farmacia, farmacia_id).cnpj)
    if licenca is None:
        return
    modelo = Usuario if qual == "usuarios" else Terminal
    em_uso = db.scalar(select(func.count()).select_from(modelo).where(modelo.ativo.is_(True))) or 0
    maximo = licenca.max_usuarios if qual == "usuarios" else licenca.max_caixas
    if maximo is not None and em_uso >= maximo:
        nome = "usuários ativos" if qual == "usuarios" else "caixas (PDVs) ativos"
        raise SemPermissao(
            f"A licença permite até {maximo} {nome}. Desative um ou peça para aumentar o limite da licença"
        )


def cnpj_da_instalacao(db: Session) -> str | None:
    """Instalado na farmácia há uma farmácia só. Antes do login, o RLS esconde a linha: usa a função do banco."""
    return db.scalar(text("SELECT * FROM licenca_cnpjs() LIMIT 1"))


def instalar(db: Session, cnpj: str, codigo: str, chave_ativacao: str | None = None) -> Licenca:
    try:
        licenca = _ler(codigo)
    except LicencaInvalida as erro:
        raise ErroDeNegocio(str(erro))
    if licenca.cnpj != cnpj:
        raise ErroDeNegocio(f"Este código é da licença do CNPJ {licenca.cnpj}, não desta farmácia")
    linha = db.get(LicencaInstalada, cnpj)
    if linha is None:
        linha = LicencaInstalada(cnpj=cnpj)
        db.add(linha)
    elif linha.emitida_em and licenca.emitida_em < linha.emitida_em:
        raise ErroDeNegocio("Este código é mais antigo do que o que já está instalado")
    linha.codigo = limpar(codigo)
    linha.emitida_em = licenca.emitida_em
    linha.ultimo_erro = None
    if chave_ativacao:
        linha.chave_ativacao = chave_ativacao
    db.commit()
    esquecer_cache()
    return licenca


def buscar_na_central(db: Session, cnpj: str, chave_ativacao: str) -> Licenca:
    """Ativa ou renova pela internet: manda a chave de ativação e o código deste servidor."""
    url = get_settings().licencas_url.rstrip("/")
    if not url:
        raise ErroDeNegocio("Este servidor não sabe o endereço da central de licenças. Cole o código da licença")
    linha = db.get(LicencaInstalada, cnpj)
    try:
        resposta = httpx.post(
            f"{url}/api/ativar",
            json={"chave_ativacao": chave_ativacao, "maquina": maquina(db)},
            timeout=20,
        )
    except httpx.HTTPError:
        if linha is not None:
            linha.ultima_tentativa_em = datetime.now(UTC)
            linha.ultimo_erro = "Sem conexão com a central de licenças"
            db.commit()
        raise ErroDeNegocio("Não foi possível falar com a central de licenças. Confira a internet")
    if resposta.status_code != 200:
        try:
            mensagem = resposta.json().get("detail") or "A central recusou o pedido"
        except ValueError:
            mensagem = "A central recusou o pedido"
        if linha is not None:
            linha.ultima_tentativa_em = datetime.now(UTC)
            linha.ultimo_erro = str(mensagem)[:300]
            db.commit()
        raise ErroDeNegocio(str(mensagem))
    licenca = instalar(db, cnpj, resposta.json()["codigo"], chave_ativacao)
    linha = db.get(LicencaInstalada, cnpj)
    linha.ultima_tentativa_em = datetime.now(UTC)
    db.commit()
    return licenca


def renovar_todas(db: Session) -> None:
    """Rodada automática: cada licença com chave de ativação pergunta à central se há código mais novo."""
    for linha in db.scalars(select(LicencaInstalada).where(LicencaInstalada.chave_ativacao.is_not(None))):
        try:
            buscar_na_central(db, linha.cnpj, linha.chave_ativacao)
        except ErroDeNegocio as erro:
            log.info("Licença %s não renovou: %s", linha.cnpj, erro.mensagem)
