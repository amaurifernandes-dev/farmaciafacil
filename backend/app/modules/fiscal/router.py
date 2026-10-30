from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response

from app.core.deps import DB, Gerente, UsuarioAtual
from app.modules.fiscal import fechamento, service
from app.modules.fiscal.provedores import ProvedorFiscal, get_provedor
from app.modules.fiscal.schemas import (
    ConfiguracaoFiscalDados,
    ConfiguracaoFiscalSaida,
    Fechamento,
    NotaFiscalSaida,
)
from app.modules.fiscal.sped import gerar_sped
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


def _download(nome: str, conteudo: bytes, tipo: str) -> Response:
    return Response(conteudo, media_type=tipo, headers={"Content-Disposition": f'attachment; filename="{nome}"'})


@router.get("/fiscal/fechamento")
def fechamento_do_mes(db: DB, _: Gerente, mes: str, loja_id: UUID | None = None) -> Fechamento:
    """Resumo fiscal do mês (AAAA-MM) de uma loja (a matriz, se não informar)."""
    return fechamento.fechamento(db, mes, loja_id)


@router.get("/fiscal/sped")
def baixar_sped(db: DB, _: Gerente, mes: str, loja_id: UUID | None = None) -> Response:
    """Arquivo do SPED Fiscal (EFD ICMS/IPI) do mês, para o contador validar no PVA e transmitir."""
    nome, conteudo = gerar_sped(db, mes, loja_id)
    return _download(nome, conteudo, "text/plain; charset=iso-8859-1")


@router.get("/fiscal/pacote")
def baixar_pacote(db: DB, _: Gerente, mes: str, loja_id: UUID | None = None) -> Response:
    """ZIP para o contador: resumo por CFOP, receita para o PGDAS, NFC-e do mês, XMLs das compras e o SPED."""
    nome, conteudo = fechamento.pacote(db, mes, loja_id)
    return _download(nome, conteudo, "application/zip")
