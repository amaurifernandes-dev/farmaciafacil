"""Serviços farmacêuticos (RDC 44/2009): aferição de pressão, glicemia, temperatura e aplicação de injetáveis."""

from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import Date, cast, func, literal_column, or_, select, text
from sqlalchemy.orm import Session

from app.core.security import TokenDados
from app.modules.auth.models import Usuario
from app.modules.clientes.models import Cliente
from app.modules.estoque.service import loja_ou_matriz
from app.modules.lojas.models import Loja
from app.modules.servicos.models import AtendimentoServico, Servico
from app.modules.servicos.regras import avaliar
from app.modules.servicos.schemas import (
    MODELOS,
    AtendimentoCriar,
    AtendimentoSaida,
    Aviso,
    ListaAtendimentos,
    ServicoAtualizar,
    ServicoCriar,
    ServicoSaida,
)
from app.modules.vendas.models import Caixa
from app.shared.datas import FUSO
from app.shared.erros import Conflito, ErroDeNegocio, NaoEncontrado

ZERO = Decimal(0)
PADRAO = [
    ("Aferição de pressão arterial", "pressao", Decimal("5.00")),
    ("Teste de glicemia capilar", "glicemia", Decimal("10.00")),
    ("Aferição de temperatura", "temperatura", Decimal(0)),
    ("Aplicação de injetável", "injetavel", Decimal("15.00")),
]


# --- Catálogo ---

def _servico_saida(s: Servico) -> ServicoSaida:
    return ServicoSaida(id=s.id, nome=s.nome, tipo=s.tipo, preco=s.preco, ativo=s.ativo)


def catalogo(db: Session, so_ativos: bool) -> list[ServicoSaida]:
    """Na primeira vez, já vem com os serviços mais comuns para a farmácia só ajustar o preço."""
    if db.scalar(select(func.count()).select_from(Servico)) == 0:
        db.add_all(Servico(nome=n, tipo=t, preco=p, ativo=True) for n, t, p in PADRAO)
        db.commit()
    consulta = select(Servico).order_by(Servico.ativo.desc(), Servico.nome)
    if so_ativos:
        consulta = consulta.where(Servico.ativo.is_(True))
    return [_servico_saida(s) for s in db.scalars(consulta)]


def _obter_servico(db: Session, servico_id: UUID) -> Servico:
    servico = db.get(Servico, servico_id)
    if servico is None:
        raise NaoEncontrado("Serviço não encontrado")
    return servico


def _nome_livre(db: Session, nome: str, ignorar: UUID | None = None) -> None:
    consulta = select(Servico.id).where(func.lower(Servico.nome) == nome.lower())
    if ignorar:
        consulta = consulta.where(Servico.id != ignorar)
    if db.scalar(consulta):
        raise Conflito("Já existe um serviço com este nome")


def criar_servico(db: Session, dados: ServicoCriar) -> ServicoSaida:
    nome = dados.nome.strip()
    _nome_livre(db, nome)
    servico = Servico(nome=nome, tipo=dados.tipo, preco=dados.preco, ativo=True)
    db.add(servico)
    db.commit()
    return _servico_saida(servico)


def atualizar_servico(db: Session, servico_id: UUID, dados: ServicoAtualizar) -> ServicoSaida:
    servico = _obter_servico(db, servico_id)
    alteracoes = dados.model_dump(exclude_unset=True, exclude_none=True)
    if "nome" in alteracoes:
        alteracoes["nome"] = alteracoes["nome"].strip()
        _nome_livre(db, alteracoes["nome"], servico.id)
    for campo, valor in alteracoes.items():
        setattr(servico, campo, valor)
    db.commit()
    return _servico_saida(servico)


# --- Atendimentos ---

def _num(valor) -> str:
    return f"{Decimal(str(valor)):.1f}".replace(".", ",")


def resultado_texto(tipo: str, r: dict) -> str:
    if tipo == "pressao":
        texto = f"{r['sistolica']} x {r['diastolica']} mmHg"
        if r.get("frequencia"):
            texto += f", {r['frequencia']} bpm"
        if r.get("braco"):
            texto += f" (braço {r['braco']})"
        return texto
    if tipo == "glicemia":
        return f"{r['valor']} mg/dL ({'em jejum' if r.get('jejum') else 'fora do jejum'})"
    if tipo == "temperatura":
        return f"{_num(r['graus'])} °C"
    if tipo == "injetavel":
        texto = f"{r['medicamento']} {r['dose']}, via {r['via']}"
        if r.get("local"):
            texto += f", {r['local']}"
        if r.get("lote"):
            texto += f", lote {r['lote']}"
        return texto
    return r.get("descricao", "")


def _saida(db: Session, a: AtendimentoServico, cache: dict | None = None) -> AtendimentoSaida:
    cache = cache if cache is not None else {}
    if a.farmaceutico_id not in cache:
        cache[a.farmaceutico_id] = db.get(Usuario, a.farmaceutico_id)
    if a.loja_id not in cache:
        cache[a.loja_id] = db.get(Loja, a.loja_id)
    farmaceutico, loja = cache[a.farmaceutico_id], cache[a.loja_id]
    aviso = avaliar(a.tipo, a.resultados)
    return AtendimentoSaida(
        id=a.id, numero=a.numero, criado_em=a.criado_em, loja_id=a.loja_id, loja_nome=loja.nome,
        servico_id=a.servico_id, servico_nome=a.servico_nome, tipo=a.tipo, cliente_id=a.cliente_id,
        paciente_nome=a.paciente_nome, paciente_cpf=a.paciente_cpf, paciente_nascimento=a.paciente_nascimento,
        farmaceutico=farmaceutico.nome, farmaceutico_crf=farmaceutico.crf, resultados=a.resultados,
        resultado_texto=resultado_texto(a.tipo, a.resultados),
        aviso=Aviso(nivel=aviso[0], texto=aviso[1]) if aviso else None,
        orientacao=a.orientacao, valor=a.valor, forma_pagamento=a.forma_pagamento, status=a.status,
        motivo_cancelamento=a.motivo_cancelamento,
    )


def _validar_resultados(tipo: str, resultados: dict) -> dict:
    try:
        return MODELOS[tipo].model_validate(resultados).model_dump(mode="json", exclude_none=True)
    except ValidationError as erro:
        primeiro = erro.errors()[0]
        campo = ".".join(str(p) for p in primeiro["loc"])
        raise ErroDeNegocio(f"Confira o resultado ({campo}): {primeiro['msg']}") from None


def registrar(db: Session, usuario: TokenDados, dados: AtendimentoCriar) -> AtendimentoSaida:
    servico = _obter_servico(db, dados.servico_id)
    if not servico.ativo:
        raise ErroDeNegocio(f"O serviço {servico.nome} está desativado")
    farmaceutico = db.get(Usuario, usuario.usuario_id)
    if not farmaceutico.crf:
        raise ErroDeNegocio(
            "Seu usuário está sem o número do CRF, que vai na declaração do serviço. "
            "Peça ao administrador para preencher em Configurações › Usuários."
        )
    loja = loja_ou_matriz(db, dados.loja_id)
    resultados = _validar_resultados(servico.tipo, dados.resultados)

    nome, cpf, nascimento = dados.paciente_nome, dados.paciente_cpf, dados.paciente_nascimento
    if dados.cliente_id is not None:
        cliente = db.get(Cliente, dados.cliente_id)
        if cliente is None:
            raise NaoEncontrado("Cliente não encontrado")
        nome, cpf, nascimento = nome or cliente.nome, cpf or cliente.cpf, nascimento or cliente.data_nascimento

    valor = ZERO if dados.forma_pagamento == "cortesia" else (dados.valor if dados.valor is not None else servico.preco)
    caixa_id = None
    if dados.forma_pagamento == "dinheiro" and valor > 0:
        caixa_id = db.scalar(select(Caixa.id).where(Caixa.usuario_id == usuario.usuario_id, Caixa.status == "aberto"))
        if caixa_id is None:
            raise ErroDeNegocio("Para receber em dinheiro, abra o seu caixa. Ou escolha Pix ou cartão.")

    # Trava a numeração da farmácia para dois atendimentos ao mesmo tempo não pegarem o mesmo número.
    db.execute(text("SELECT pg_advisory_xact_lock(hashtext('servico:' || current_setting('app.farmacia_id')))"))
    numero = (db.scalar(select(func.max(AtendimentoServico.numero))) or 0) + 1
    atendimento = AtendimentoServico(
        numero=numero, loja_id=loja.id, servico_id=servico.id, servico_nome=servico.nome, tipo=servico.tipo,
        cliente_id=dados.cliente_id, paciente_nome=nome.strip(), paciente_cpf=cpf, paciente_nascimento=nascimento,
        farmaceutico_id=usuario.usuario_id, resultados=resultados,
        orientacao=(dados.orientacao or "").strip() or None, valor=valor, forma_pagamento=dados.forma_pagamento,
        caixa_id=caixa_id, status="registrado",
    )
    db.add(atendimento)
    db.commit()
    return _saida(db, atendimento)


def obter(db: Session, atendimento_id: UUID) -> AtendimentoSaida:
    atendimento = db.get(AtendimentoServico, atendimento_id)
    if atendimento is None:
        raise NaoEncontrado("Atendimento não encontrado")
    return _saida(db, atendimento)


def listar(
    db: Session, inicio: date, fim: date, loja_id: UUID | None, cliente_id: UUID | None, busca: str | None
) -> ListaAtendimentos:
    dia = cast(func.timezone(literal_column(f"'{FUSO.key}'"), AtendimentoServico.criado_em), Date)
    consulta = select(AtendimentoServico).where(dia.between(inicio, fim))
    if loja_id:
        consulta = consulta.where(AtendimentoServico.loja_id == loja_id)
    if cliente_id:
        consulta = consulta.where(AtendimentoServico.cliente_id == cliente_id)
    if busca and busca.strip():
        termo = busca.strip()
        consulta = consulta.where(or_(AtendimentoServico.paciente_nome.ilike(f"%{termo}%"),
                                      AtendimentoServico.paciente_cpf == "".join(c for c in termo if c.isdigit())))
    atendimentos = db.scalars(consulta.order_by(AtendimentoServico.criado_em.desc()).limit(500)).all()
    cache: dict = {}
    itens = [_saida(db, a, cache) for a in atendimentos]
    validos = [a for a in itens if a.status == "registrado"]
    por_servico: dict[str, int] = {}
    for a in validos:
        por_servico[a.servico_nome] = por_servico.get(a.servico_nome, 0) + 1
    return ListaAtendimentos(itens=itens, total_recebido=sum((a.valor for a in validos), ZERO),
                             por_servico=por_servico)


def do_cliente(db: Session, cliente_id: UUID) -> list[AtendimentoSaida]:
    atendimentos = db.scalars(
        select(AtendimentoServico)
        .where(AtendimentoServico.cliente_id == cliente_id, AtendimentoServico.status == "registrado")
        .order_by(AtendimentoServico.criado_em.desc()).limit(100)
    ).all()
    cache: dict = {}
    return [_saida(db, a, cache) for a in atendimentos]


def cancelar(db: Session, atendimento_id: UUID, motivo: str) -> AtendimentoSaida:
    atendimento = db.scalar(select(AtendimentoServico).where(AtendimentoServico.id == atendimento_id).with_for_update())
    if atendimento is None:
        raise NaoEncontrado("Atendimento não encontrado")
    if atendimento.status == "cancelado":
        raise Conflito("Este atendimento já foi cancelado")
    if atendimento.caixa_id:
        caixa = db.get(Caixa, atendimento.caixa_id)
        if caixa.status != "aberto":
            raise ErroDeNegocio("O caixa em que o dinheiro entrou já foi fechado. Devolva o valor pelo caixa de hoje.")
    atendimento.status = "cancelado"
    atendimento.motivo_cancelamento = motivo.strip()
    db.commit()
    return _saida(db, atendimento)


def recebido_no_caixa(db: Session, caixa_id: UUID) -> Decimal:
    """Dinheiro de serviços que entrou na gaveta deste caixa."""
    return db.scalar(
        select(func.coalesce(func.sum(AtendimentoServico.valor), 0))
        .where(AtendimentoServico.caixa_id == caixa_id, AtendimentoServico.status == "registrado")
    )
