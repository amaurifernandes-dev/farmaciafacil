from uuid import UUID

from fastapi import APIRouter, Response, status

from app.core.deps import DB, Gerente, UsuarioAtual
from app.modules.financeiro.schemas import ContaSaida
from app.modules.financeiro.service import saida as conta_saida
from app.modules.popular import service
from app.modules.popular.schemas import Lancar, Mes, MesPopular, VendaPopularSaida

router = APIRouter(prefix="/popular", tags=["farmacia popular"])


@router.get("", response_model=MesPopular, summary="Vendas do mês pela Farmácia Popular e quanto o governo deve")
def do_mes(db: DB, _: Gerente, mes: Mes) -> MesPopular:
    return service.resumo_do_mes(db, mes)


@router.get("/venda/{venda_id}", response_model=VendaPopularSaida, summary="Dados da Farmácia Popular de uma venda")
def da_venda(db: DB, _: UsuarioAtual, venda_id: UUID) -> VendaPopularSaida:
    return service.da_venda(db, venda_id)


@router.post("/lancar", response_model=ContaSaida, status_code=status.HTTP_201_CREATED,
             summary="Lança no Financeiro, como conta a receber, a parte do governo das vendas do mês")
def lancar(db: DB, usuario: Gerente, dados: Lancar) -> ContaSaida:
    return conta_saida(db, service.lancar_mes(db, usuario, dados.mes))


@router.post("/lancamentos/{conta_id}/desfazer", status_code=status.HTTP_204_NO_CONTENT,
             summary="Cancela o lançamento não recebido; as vendas voltam a ficar em aberto")
def desfazer(db: DB, _: Gerente, conta_id: UUID) -> None:
    service.desfazer(db, conta_id)


@router.get("/planilha", summary="Planilha (CSV) das vendas do mês, para conferir e guardar")
def planilha(db: DB, _: Gerente, mes: Mes) -> Response:
    nome, conteudo = service.planilha_csv(db, mes)
    return Response(conteudo, media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{nome}"'})
