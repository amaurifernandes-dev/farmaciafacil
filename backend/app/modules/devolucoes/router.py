from datetime import date, timedelta
from uuid import UUID

from fastapi import APIRouter, status

from app.core.deps import DB, Gerente, Operador
from app.modules.devolucoes import service
from app.modules.devolucoes.schemas import (
    DevolucaoCriar,
    DevolucaoSaida,
    ListaDevolucoes,
    ValeSaida,
    VendaParaDevolver,
)
from app.modules.lojas.deps import TerminalAtual
from app.shared.datas import hoje
from app.shared.erros import ErroDeNegocio

router = APIRouter(prefix="/devolucoes", tags=["trocas e devoluções"])
vales = APIRouter(prefix="/vales", tags=["trocas e devoluções"])


@router.get("/venda", response_model=VendaParaDevolver, summary="Itens da venda que ainda podem ser devolvidos")
def venda(db: DB, _: Gerente, numero: int | None = None, venda_id: UUID | None = None) -> VendaParaDevolver:
    return service.para_devolver(db, venda_id, numero)


@router.post("", status_code=status.HTTP_201_CREATED, response_model=DevolucaoSaida,
             summary="Devolve itens de uma venda, em dinheiro ou em vale-troca")
def registrar(db: DB, usuario: Gerente, terminal: TerminalAtual, dados: DevolucaoCriar) -> DevolucaoSaida:
    return service.registrar(db, usuario, terminal, dados)


@router.get("", response_model=ListaDevolucoes, summary="Devoluções do período")
def listar(
    db: DB, _: Gerente, inicio: date | None = None, fim: date | None = None, loja_id: UUID | None = None
) -> ListaDevolucoes:
    fim = fim or hoje()
    inicio = inicio or fim.replace(day=1)
    if inicio > fim:
        raise ErroDeNegocio("O início do período não pode ser depois do fim")
    if fim - inicio > timedelta(days=366):
        raise ErroDeNegocio("Escolha um período de até um ano")
    return service.listar(db, inicio, fim, loja_id)


@router.get("/{devolucao_id}", response_model=DevolucaoSaida, summary="Uma devolução (para o comprovante)")
def obter(db: DB, _: Gerente, devolucao_id: UUID) -> DevolucaoSaida:
    return service.obter(db, devolucao_id)


@vales.get("/{codigo}", response_model=ValeSaida, summary="Saldo e validade de um vale-troca (no PDV)")
def consultar(db: DB, _: Operador, codigo: str) -> ValeSaida:
    return service.consultar_vale(db, codigo)
