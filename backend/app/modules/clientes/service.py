from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.clientes.models import Cliente
from app.modules.clientes.schemas import ClienteAtualizar, ClienteCriar
from app.shared.erros import Conflito, NaoEncontrado


def listar(db: Session, busca: str | None, pagina: int, por_pagina: int, incluir_inativos: bool):
    filtro = select(Cliente)
    if not incluir_inativos:
        filtro = filtro.where(Cliente.ativo.is_(True))
    if busca and busca.strip():
        termo = busca.strip()
        digitos = "".join(c for c in termo if c.isdigit())
        condicoes = [Cliente.nome.ilike(f"%{termo}%")]
        if digitos:
            condicoes += [Cliente.cpf == digitos, Cliente.telefone.like(f"%{digitos}%")]
        filtro = filtro.where(or_(*condicoes))
    total = db.scalar(select(func.count()).select_from(filtro.subquery()))
    itens = db.scalars(filtro.order_by(Cliente.nome).offset((pagina - 1) * por_pagina).limit(por_pagina)).all()
    return itens, total


def obter(db: Session, cliente_id: UUID) -> Cliente:
    cliente = db.get(Cliente, cliente_id)
    if cliente is None:
        raise NaoEncontrado("Cliente não encontrado")
    return cliente


def _registrar_consentimento(cliente: Cliente, aceita: bool) -> None:
    # Guarda quando o cliente autorizou; ao retirar a autorização, o registro é limpo.
    if aceita and not cliente.aceita_ofertas:
        cliente.consentimento_em = datetime.now(timezone.utc)
    if not aceita:
        cliente.consentimento_em = None
    cliente.aceita_ofertas = aceita


def _salvar(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise Conflito("Já existe cliente com este CPF")


def criar(db: Session, dados: ClienteCriar) -> Cliente:
    cliente = Cliente(**dados.model_dump(exclude={"aceita_ofertas"}), aceita_ofertas=False)
    _registrar_consentimento(cliente, dados.aceita_ofertas)
    db.add(cliente)
    _salvar(db)
    return cliente


def atualizar(db: Session, cliente_id: UUID, dados: ClienteAtualizar) -> Cliente:
    cliente = obter(db, cliente_id)
    alteracoes = dados.model_dump(exclude_unset=True)
    aceita = alteracoes.pop("aceita_ofertas", None)
    if aceita is not None:
        _registrar_consentimento(cliente, aceita)
    for campo, valor in alteracoes.items():
        if campo in ("nome", "ativo") and valor is None:
            continue
        setattr(cliente, campo, valor)
    _salvar(db)
    db.refresh(cliente)
    return cliente
