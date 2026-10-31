from datetime import date, timedelta
from uuid import UUID

from fastapi import APIRouter, Response

from app.core.deps import DB, Gerente, UsuarioAtual
from app.modules.comissoes import service
from app.modules.comissoes.schemas import DetalheVendedor, RelatorioComissoes
from app.shared.datas import hoje
from app.shared.erros import ErroDeNegocio, SemPermissao

router = APIRouter(prefix="/comissoes", tags=["comissões"])
GERENTES = ("admin", "gerente")


def _periodo(inicio: date | None, fim: date | None) -> tuple[date, date]:
    """Sem datas: o mês atual até hoje."""
    fim = fim or hoje()
    inicio = inicio or fim.replace(day=1)
    if inicio > fim:
        raise ErroDeNegocio("O início do período não pode ser depois do fim")
    if fim - inicio > timedelta(days=366):
        raise ErroDeNegocio("Escolha um período de até um ano")
    return inicio, fim


@router.get("", response_model=RelatorioComissoes, summary="Vendas e comissão de cada vendedor no período")
def relatorio(
    db: DB, usuario: Gerente, inicio: date | None = None, fim: date | None = None, loja_id: UUID | None = None
) -> RelatorioComissoes:
    return service.relatorio(db, usuario.farmacia_id, *_periodo(inicio, fim), loja_id)


@router.get("/planilha", summary="Planilha (CSV) das comissões do período")
def planilha(
    db: DB, usuario: Gerente, inicio: date | None = None, fim: date | None = None, loja_id: UUID | None = None
) -> Response:
    nome, conteudo = service.planilha_csv(db, usuario.farmacia_id, *_periodo(inicio, fim), loja_id)
    return Response(conteudo, media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{nome}"'})


@router.get("/minhas", response_model=DetalheVendedor, summary="As vendas e a comissão de quem está usando")
def minhas(db: DB, usuario: UsuarioAtual, inicio: date | None = None, fim: date | None = None) -> DetalheVendedor:
    return service.detalhe(db, usuario.farmacia_id, usuario.usuario_id, *_periodo(inicio, fim), None)


@router.get("/vendedor/{usuario_id}", response_model=DetalheVendedor, summary="Vendas e produtos de um vendedor")
def detalhe(
    db: DB,
    usuario: UsuarioAtual,
    usuario_id: UUID,
    inicio: date | None = None,
    fim: date | None = None,
    loja_id: UUID | None = None,
) -> DetalheVendedor:
    if usuario.papel not in GERENTES and usuario.usuario_id != usuario_id:
        raise SemPermissao("Você só pode ver as suas próprias vendas")
    return service.detalhe(db, usuario.farmacia_id, usuario_id, *_periodo(inicio, fim), loja_id)
