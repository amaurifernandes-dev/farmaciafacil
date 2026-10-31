from datetime import date, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.core.deps import DB, Gerente, UsuarioAtual, exigir_papel
from app.core.security import TokenDados
from app.modules.servicos import service
from app.modules.servicos.schemas import (
    AtendimentoCriar,
    AtendimentoSaida,
    Cancelar,
    ListaAtendimentos,
    ServicoAtualizar,
    ServicoCriar,
    ServicoSaida,
)
from app.shared.datas import hoje
from app.shared.erros import ErroDeNegocio

router = APIRouter(prefix="/servicos", tags=["serviços farmacêuticos"])
# Quem faz e registra o serviço: o farmacêutico (ou o dono/gerente que também é farmacêutico).
Farmaceutico = Annotated[TokenDados, Depends(exigir_papel("admin", "gerente", "farmaceutico"))]


@router.get("", response_model=list[ServicoSaida], summary="Serviços que a farmácia oferece")
def catalogo(db: DB, _: UsuarioAtual, todos: bool = False) -> list[ServicoSaida]:
    return service.catalogo(db, so_ativos=not todos)


@router.post("", status_code=status.HTTP_201_CREATED, response_model=ServicoSaida, summary="Novo serviço")
def criar(db: DB, _: Gerente, dados: ServicoCriar) -> ServicoSaida:
    return service.criar_servico(db, dados)


@router.patch("/{servico_id}", response_model=ServicoSaida, summary="Muda nome, preço ou desativa")
def atualizar(db: DB, _: Gerente, servico_id: UUID, dados: ServicoAtualizar) -> ServicoSaida:
    return service.atualizar_servico(db, servico_id, dados)


@router.get("/atendimentos", response_model=ListaAtendimentos, summary="Atendimentos do período")
def listar(
    db: DB,
    _: Farmaceutico,
    inicio: date | None = None,
    fim: date | None = None,
    loja_id: UUID | None = None,
    cliente_id: UUID | None = None,
    busca: str | None = None,
) -> ListaAtendimentos:
    fim = fim or hoje()
    inicio = inicio or fim.replace(day=1)
    if inicio > fim:
        raise ErroDeNegocio("O início do período não pode ser depois do fim")
    if fim - inicio > timedelta(days=366):
        raise ErroDeNegocio("Escolha um período de até um ano")
    return service.listar(db, inicio, fim, loja_id, cliente_id, busca)


@router.post("/atendimentos", status_code=status.HTTP_201_CREATED, response_model=AtendimentoSaida,
             summary="Registra um serviço feito")
def registrar(db: DB, usuario: Farmaceutico, dados: AtendimentoCriar) -> AtendimentoSaida:
    return service.registrar(db, usuario, dados)


@router.get("/atendimentos/{atendimento_id}", response_model=AtendimentoSaida, summary="Um atendimento")
def obter(db: DB, _: Farmaceutico, atendimento_id: UUID) -> AtendimentoSaida:
    return service.obter(db, atendimento_id)


@router.post("/atendimentos/{atendimento_id}/cancelar", response_model=AtendimentoSaida,
             summary="Cancela um atendimento registrado errado")
def cancelar(db: DB, _: Farmaceutico, atendimento_id: UUID, dados: Cancelar) -> AtendimentoSaida:
    return service.cancelar(db, atendimento_id, dados.motivo)


@router.get("/cliente/{cliente_id}", response_model=list[AtendimentoSaida],
            summary="Histórico de serviços do cliente (ex.: as pressões medidas)")
def do_cliente(db: DB, _: Farmaceutico, cliente_id: UUID) -> list[AtendimentoSaida]:
    return service.do_cliente(db, cliente_id)
