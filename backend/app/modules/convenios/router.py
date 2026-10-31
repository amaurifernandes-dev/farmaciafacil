from uuid import UUID

from fastapi import APIRouter, Response, status

from app.core.deps import DB, Gerente, UsuarioAtual
from app.modules.convenios import service
from app.modules.convenios.schemas import (
    ConvenioAtualizar,
    ConvenioCriar,
    ConvenioDetalhe,
    ConvenioDoCliente,
    ConvenioResumo,
    ConvenioSaida,
    Fechar,
)
from app.modules.financeiro.schemas import ContaSaida
from app.modules.financeiro.service import saida as conta_saida

router = APIRouter(prefix="/convenios", tags=["convenios"])


@router.get("", response_model=list[ConvenioResumo], summary="Empresas conveniadas, com o que está em aberto")
def listar(db: DB, _: UsuarioAtual, incluir_inativos: bool = False) -> list[ConvenioResumo]:
    return service.listar(db, incluir_inativos)


@router.post("", response_model=ConvenioSaida, status_code=status.HTTP_201_CREATED)
def criar(db: DB, _: Gerente, dados: ConvenioCriar):
    return service.criar(db, dados)


@router.get("/cliente/{cliente_id}", response_model=ConvenioDoCliente, summary="Convênio, desconto e limite do cliente")
def do_cliente(db: DB, _: UsuarioAtual, cliente_id: UUID) -> ConvenioDoCliente:
    return service.do_cliente(db, cliente_id)


@router.post("/faturas/{conta_id}/desfazer", status_code=status.HTTP_204_NO_CONTENT,
             summary="Cancela a fatura não paga; as compras voltam para o próximo fechamento")
def desfazer(db: DB, _: Gerente, conta_id: UUID) -> None:
    service.desfazer(db, conta_id)


@router.get("/{convenio_id}", response_model=ConvenioDetalhe)
def detalhe(db: DB, _: Gerente, convenio_id: UUID) -> ConvenioDetalhe:
    return service.detalhe(db, convenio_id)


@router.patch("/{convenio_id}", response_model=ConvenioSaida)
def atualizar(db: DB, _: Gerente, convenio_id: UUID, dados: ConvenioAtualizar):
    return service.atualizar(db, convenio_id, dados)


@router.post("/{convenio_id}/fechar", response_model=ContaSaida, status_code=status.HTTP_201_CREATED,
             summary="Fecha o mês: junta as compras numa conta a receber da empresa")
def fechar(db: DB, usuario: Gerente, convenio_id: UUID, dados: Fechar) -> ContaSaida:
    return conta_saida(db, service.fechar(db, usuario, convenio_id, dados.ate))


@router.get("/{convenio_id}/extrato", summary="Planilha (CSV) por funcionário, para a empresa descontar na folha")
def extrato(db: DB, _: Gerente, convenio_id: UUID, conta_id: UUID | None = None) -> Response:
    nome, conteudo = service.extrato_csv(db, convenio_id, conta_id)
    return Response(conteudo, media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{nome}"'})
