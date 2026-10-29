from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from app.core.deps import DB, Gerente, UsuarioAtual
from app.modules.fiscal import service
from app.modules.fiscal.provedores import ProvedorFiscal, get_provedor
from app.modules.fiscal.schemas import ConfiguracaoFiscalDados, ConfiguracaoFiscalSaida, NotaFiscalSaida
from app.modules.vendas.service import obter_venda
from app.shared.erros import NaoEncontrado

Provedor = Annotated[ProvedorFiscal | None, Depends(get_provedor)]

router = APIRouter(tags=["fiscal"])


@router.get("/fiscal/configuracao")
def obter_configuracao(db: DB, _: Gerente) -> ConfiguracaoFiscalSaida:
    config = service.obter_configuracao(db)
    if config is None:
        raise NaoEncontrado("Dados fiscais ainda não configurados")
    return config


@router.put("/fiscal/configuracao")
def salvar_configuracao(db: DB, _: Gerente, dados: ConfiguracaoFiscalDados) -> ConfiguracaoFiscalSaida:
    return service.salvar_configuracao(db, dados)


@router.post("/vendas/{venda_id}/nfce")
def emitir(db: DB, _: UsuarioAtual, provedor: Provedor, venda_id: UUID) -> NotaFiscalSaida:
    """Emite a NFC-e da venda, ou reenvia uma que falhou. Se já estiver autorizada, só devolve."""
    return service.emitir_nfce(db, provedor, obter_venda(db, venda_id))


@router.get("/vendas/{venda_id}/nfce")
def consultar(db: DB, provedor: Provedor, venda_id: UUID, atualizar: bool = False) -> NotaFiscalSaida:
    """Com atualizar=true, pergunta ao provedor o resultado de uma nota que ficou em processamento."""
    return service.consultar_nfce(db, provedor, obter_venda(db, venda_id), atualizar)
