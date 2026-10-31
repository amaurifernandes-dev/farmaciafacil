"""Financeiro: contas a pagar e a receber, crédito do cliente (fiado) e fluxo de caixa."""

from collections import defaultdict
from datetime import date, timedelta
from decimal import ROUND_DOWN, Decimal
from uuid import UUID

from sqlalchemy import Date, case, cast, func, or_, select
from sqlalchemy.orm import Session

from app.core.security import TokenDados
from app.modules.clientes.models import Cliente
from app.modules.compras.nfe_xml import ler_nfe
from app.modules.convenios.models import Convenio
from app.modules.financeiro.models import CATEGORIAS, Conta
from app.modules.financeiro.schemas import (
    ContaAtualizar,
    ContaBaixar,
    ContaCriar,
    ContaSaida,
    CreditoCliente,
    DiaFluxo,
    FluxoCaixa,
    PaginaContas,
    Totais,
)
from app.modules.fornecedores.models import Fornecedor
from app.modules.lojas.service import matriz, obter_loja
from app.modules.vendas.models import Caixa, Venda, VendaPagamento
from app.shared.datas import FUSO, hoje, mais_meses
from app.shared.erros import Conflito, ErroDeNegocio, NaoEncontrado

CENTAVO = Decimal("0.01")
ZERO = Decimal(0)


def _dividir(total: Decimal, partes: int) -> list[Decimal]:
    """Divide em parcelas iguais; os centavos que sobram vão na primeira."""
    parte = (total / partes).quantize(CENTAVO, rounding=ROUND_DOWN)
    return [total - parte * (partes - 1)] + [parte] * (partes - 1)


def _validar_categoria(tipo: str, categoria: str) -> None:
    if categoria not in CATEGORIAS[tipo]:
        raise ErroDeNegocio("Categoria inválida")


# --- Lançamento ---

def criar(db: Session, usuario: TokenDados, dados: ContaCriar) -> list[Conta]:
    _validar_categoria(dados.tipo, dados.categoria)
    loja = obter_loja(db, dados.loja_id) if dados.loja_id else matriz(db)
    if dados.fornecedor_id and db.get(Fornecedor, dados.fornecedor_id) is None:
        raise NaoEncontrado("Fornecedor não encontrado")
    if dados.cliente_id and db.get(Cliente, dados.cliente_id) is None:
        raise NaoEncontrado("Cliente não encontrado")

    contas = [
        Conta(
            tipo=dados.tipo,
            loja_id=loja.id,
            descricao=dados.descricao.strip(),
            categoria=dados.categoria,
            fornecedor_id=dados.fornecedor_id,
            cliente_id=dados.cliente_id,
            documento=dados.documento,
            parcela=numero,
            parcelas=dados.parcelas,
            valor=valor,
            vencimento=mais_meses(dados.primeiro_vencimento, numero - 1),
            observacao=dados.observacao,
            usuario_id=usuario.usuario_id,
        )
        for numero, valor in enumerate(_dividir(dados.valor_total, dados.parcelas), start=1)
    ]
    db.add_all(contas)
    db.commit()
    return contas


def contas_da_nota(db: Session, usuario_id: UUID, nota) -> list[Conta]:
    """Contas a pagar de uma nota de compra confirmada, pelas parcelas (duplicatas) do XML.

    Sem parcelas no XML, lança o valor total vencendo na data de emissão, para a pessoa ajustar.
    Não faz commit: entra na mesma transação da confirmação da nota.
    """
    lida = ler_nfe(nota.xml)
    parcelas = [(d.numero, d.vencimento, d.valor) for d in lida.duplicatas]
    if not parcelas:
        parcelas = [(None, nota.emitida_em.astimezone(FUSO).date(), nota.valor_total)]
    fornecedor = nota.fornecedor.nome_fantasia or nota.fornecedor.razao_social
    contas = [
        Conta(
            tipo="pagar",
            loja_id=nota.loja_id,
            descricao=f"NF {nota.numero} - {fornecedor}"[:200],
            categoria="fornecedores",
            fornecedor_id=nota.fornecedor_id,
            documento=(numero or str(nota.numero))[:60],
            parcela=indice,
            parcelas=len(parcelas),
            valor=valor,
            vencimento=vencimento,
            nota_entrada_id=nota.id,
            usuario_id=usuario_id,
        )
        for indice, (numero, vencimento, valor) in enumerate(parcelas, start=1)
    ]
    db.add_all(contas)
    return contas


# --- Fiado (venda a prazo) ---

def em_aberto_do_cliente(db: Session, cliente_id: UUID) -> Decimal:
    return db.scalar(
        select(func.coalesce(func.sum(Conta.valor), 0)).where(
            Conta.tipo == "receber", Conta.status == "aberta", Conta.cliente_id == cliente_id
        )
    )


def lancar_fiado(
    db: Session, usuario_id: UUID, venda: Venda, loja_id: UUID, valor: Decimal, vencimento: date | None, dias_padrao: int
) -> Conta:
    """Confere o limite do cliente e lança a conta a receber da venda. Não faz commit."""
    if venda.cliente_id is None:
        raise ErroDeNegocio("Escolha o cliente para vender a prazo")
    # Trava o cliente: duas vendas a prazo ao mesmo tempo não passam juntas do limite.
    cliente = db.scalar(select(Cliente).where(Cliente.id == venda.cliente_id).with_for_update())
    if cliente is None or not cliente.ativo:
        raise NaoEncontrado("Cliente não encontrado")
    limite = cliente.limite_credito or ZERO
    if limite <= 0:
        raise ErroDeNegocio(f"{cliente.nome} não tem limite para comprar a prazo. Defina o limite no cadastro do cliente.")
    disponivel = limite - em_aberto_do_cliente(db, cliente.id)
    if valor > disponivel:
        raise ErroDeNegocio(f"Limite de {cliente.nome} insuficiente: disponível R$ {max(disponivel, ZERO):.2f}")
    vencimento = vencimento or hoje() + timedelta(days=dias_padrao)
    if vencimento < hoje():
        raise ErroDeNegocio("O vencimento da venda a prazo não pode ser no passado")

    conta = Conta(
        tipo="receber",
        loja_id=loja_id,
        descricao=f"Venda nº {venda.numero} a prazo",
        categoria="venda_prazo",
        cliente_id=cliente.id,
        documento=str(venda.numero),
        valor=valor,
        vencimento=vencimento,
        venda_id=venda.id,
        usuario_id=usuario_id,
    )
    db.add(conta)
    return conta


def cancelar_fiado_da_venda(db: Session, venda: Venda) -> None:
    """Na venda cancelada, a conta a receber some. Se já foi recebida, é preciso estornar antes."""
    contas = db.scalars(select(Conta).where(Conta.venda_id == venda.id, Conta.status != "cancelada")).all()
    if any(c.status == "paga" for c in contas):
        raise Conflito(
            "O valor a prazo desta venda já foi recebido. Estorne o recebimento em Financeiro antes de cancelar."
        )
    for conta in contas:
        conta.status = "cancelada"


def credito_do_cliente(db: Session, cliente_id: UUID) -> CreditoCliente:
    cliente = db.get(Cliente, cliente_id)
    if cliente is None:
        raise NaoEncontrado("Cliente não encontrado")
    abertas = db.scalars(
        select(Conta)
        .where(Conta.tipo == "receber", Conta.status == "aberta", Conta.cliente_id == cliente_id)
        .order_by(Conta.vencimento)
    ).all()
    em_aberto = sum((c.valor for c in abertas), ZERO)
    limite = cliente.limite_credito or ZERO
    return CreditoCliente(
        cliente_id=cliente.id,
        nome=cliente.nome,
        limite=limite,
        em_aberto=em_aberto,
        disponivel=max(limite - em_aberto, ZERO),
        vencido=sum((c.valor for c in abertas if c.vencimento < hoje()), ZERO),
        contas=saidas(db, abertas),
    )


# --- Consulta ---

def saidas(db: Session, contas: list[Conta]) -> list[ContaSaida]:
    fornecedores = {c.fornecedor_id for c in contas if c.fornecedor_id}
    clientes = {c.cliente_id for c in contas if c.cliente_id}
    nomes: dict[UUID, str] = {}
    if fornecedores:
        nomes |= dict(
            db.execute(
                select(Fornecedor.id, func.coalesce(Fornecedor.nome_fantasia, Fornecedor.razao_social))
                .where(Fornecedor.id.in_(fornecedores))
            ).all()
        )
    if clientes:
        nomes |= dict(db.execute(select(Cliente.id, Cliente.nome).where(Cliente.id.in_(clientes))).all())
    convenios = {c.convenio_id for c in contas if c.convenio_id}
    if convenios:
        nomes |= dict(db.execute(select(Convenio.id, Convenio.nome).where(Convenio.id.in_(convenios))).all())
    dia = hoje()
    return [
        ContaSaida.model_validate(c).model_copy(
            update={
                "pessoa": nomes.get(c.fornecedor_id or c.cliente_id or c.convenio_id),
                "vencida": c.status == "aberta" and c.vencimento < dia,
            }
        )
        for c in contas
    ]


def totais(db: Session, tipo: str, loja_id: UUID | None = None) -> Totais:
    dia = hoje()
    inicio_mes = dia.replace(day=1)
    abertas = (Conta.tipo == tipo) & (Conta.status == "aberta")
    filtro = select(
        func.coalesce(func.sum(case((abertas & (Conta.vencimento < dia), Conta.valor))), 0),
        func.count().filter(abertas & (Conta.vencimento < dia)),
        func.coalesce(func.sum(case((abertas & (Conta.vencimento == dia), Conta.valor))), 0),
        func.coalesce(
            func.sum(case((abertas & Conta.vencimento.between(dia, dia + timedelta(days=7)), Conta.valor))), 0
        ),
        func.coalesce(func.sum(case((abertas, Conta.valor))), 0),
        func.coalesce(
            func.sum(
                case(((Conta.tipo == tipo) & (Conta.status == "paga") & (Conta.pago_em >= inicio_mes), Conta.valor_pago))
            ),
            0,
        ),
    )
    if loja_id is not None:
        filtro = filtro.where(Conta.loja_id == loja_id)
    vencidas, quantidade, vence_hoje, proximos, em_aberto, pago = db.execute(filtro).one()
    return Totais(
        vencidas=vencidas,
        quantidade_vencidas=quantidade,
        vence_hoje=vence_hoje,
        proximos_7_dias=proximos,
        em_aberto=em_aberto,
        pago_no_mes=pago,
    )


def listar(
    db: Session,
    tipo: str,
    situacao: str,
    inicio: date | None,
    fim: date | None,
    busca: str | None,
    loja_id: UUID | None,
    pagina: int,
    por_pagina: int,
) -> PaginaContas:
    filtro = select(Conta).where(Conta.tipo == tipo)
    dia = hoje()
    # Contas pagas são filtradas pela data do pagamento; as outras, pelo vencimento.
    data = Conta.pago_em if situacao == "pagas" else Conta.vencimento
    if situacao == "abertas":
        filtro = filtro.where(Conta.status == "aberta")
    elif situacao == "vencidas":
        filtro = filtro.where(Conta.status == "aberta", Conta.vencimento < dia)
    elif situacao == "pagas":
        filtro = filtro.where(Conta.status == "paga")
    elif situacao == "canceladas":
        filtro = filtro.where(Conta.status == "cancelada")
    if inicio:
        filtro = filtro.where(data >= inicio)
    if fim:
        filtro = filtro.where(data <= fim)
    if loja_id:
        filtro = filtro.where(Conta.loja_id == loja_id)
    if busca and busca.strip():
        termo = f"%{busca.strip()}%"
        pessoas = select(Fornecedor.id).where(
            or_(Fornecedor.razao_social.ilike(termo), Fornecedor.nome_fantasia.ilike(termo))
        ).union(select(Cliente.id).where(Cliente.nome.ilike(termo)))
        filtro = filtro.where(
            or_(
                Conta.descricao.ilike(termo),
                Conta.documento.ilike(termo),
                Conta.fornecedor_id.in_(pessoas),
                Conta.cliente_id.in_(pessoas),
            )
        )

    sub = filtro.subquery()
    total, soma = db.execute(select(func.count(), func.coalesce(func.sum(sub.c.valor), 0))).one()
    ordem = (Conta.pago_em.desc(), Conta.id.desc()) if situacao == "pagas" else (Conta.vencimento, Conta.id)
    contas = db.scalars(filtro.order_by(*ordem).offset((pagina - 1) * por_pagina).limit(por_pagina)).all()
    return PaginaContas(
        itens=saidas(db, contas), total=total, soma=soma, totais=totais(db, tipo, loja_id)
    )


def obter(db: Session, conta_id: UUID, travar: bool = False) -> Conta:
    filtro = select(Conta).where(Conta.id == conta_id)
    if travar:
        filtro = filtro.with_for_update()
    conta = db.scalar(filtro)
    if conta is None:
        raise NaoEncontrado("Conta não encontrada")
    return conta


def saida(db: Session, conta: Conta) -> ContaSaida:
    return saidas(db, [conta])[0]


# --- Alterações ---

def _aberta(db: Session, conta_id: UUID) -> Conta:
    conta = obter(db, conta_id, travar=True)
    if conta.status != "aberta":
        raise Conflito("Esta conta já foi paga ou cancelada")
    return conta


def atualizar(db: Session, conta_id: UUID, dados: ContaAtualizar) -> Conta:
    conta = _aberta(db, conta_id)
    alteracoes = dados.model_dump(exclude_unset=True)
    for campo in ("descricao", "categoria", "valor", "vencimento"):
        if campo in alteracoes and alteracoes[campo] is None:
            raise ErroDeNegocio(f"O campo {campo} é obrigatório")
    if "categoria" in alteracoes:
        _validar_categoria(conta.tipo, alteracoes["categoria"])
    if conta.venda_id and "valor" in alteracoes:
        raise ErroDeNegocio("O valor de uma venda a prazo só muda cancelando a venda")
    if conta.convenio_id and "valor" in alteracoes:
        raise ErroDeNegocio("O valor da fatura do convênio vem das compras. Desfaça a fatura em Convênios para mudar.")
    for campo, valor in alteracoes.items():
        setattr(conta, campo, valor)
    db.commit()
    return conta


def baixar(db: Session, usuario: TokenDados, conta_id: UUID, dados: ContaBaixar, caixa: Caixa | None) -> Conta:
    """Marca como paga (ou recebida). Dinheiro recebido num caixa aberto entra na conferência dele."""
    conta = _aberta(db, conta_id)
    pago_em = dados.pago_em or hoje()
    if pago_em > hoje():
        raise ErroDeNegocio("A data do pagamento não pode ser no futuro")
    conta.status = "paga"
    conta.pago_em = pago_em
    conta.valor_pago = dados.valor_pago or conta.valor
    conta.forma_pagamento = dados.forma_pagamento
    conta.baixada_por = usuario.usuario_id
    if dados.observacao:
        conta.observacao = dados.observacao
    if conta.tipo == "receber" and dados.forma_pagamento == "dinheiro" and caixa is not None:
        conta.caixa_id = caixa.id
    db.commit()
    return conta


def estornar(db: Session, conta_id: UUID) -> Conta:
    """Desfaz o pagamento: a conta volta a ficar em aberto."""
    conta = obter(db, conta_id, travar=True)
    if conta.status != "paga":
        raise Conflito("Só uma conta paga pode ser estornada")
    if conta.caixa_id is not None:
        caixa = db.get(Caixa, conta.caixa_id)
        if caixa is not None and caixa.status != "aberto":
            raise Conflito("Este recebimento entrou num caixa que já foi fechado e não pode ser estornado")
    conta.status = "aberta"
    conta.pago_em = None
    conta.valor_pago = None
    conta.forma_pagamento = None
    conta.baixada_por = None
    conta.caixa_id = None
    db.commit()
    return conta


def cancelar(db: Session, conta_id: UUID) -> Conta:
    conta = _aberta(db, conta_id)
    if conta.venda_id is not None:
        raise ErroDeNegocio("Para cancelar uma venda a prazo, cancele a venda")
    if conta.convenio_id is not None:
        raise ErroDeNegocio("Para cancelar a fatura de um convênio, use Desfazer fatura em Convênios")
    conta.status = "cancelada"
    db.commit()
    return conta


def recebido_no_caixa(db: Session, caixa_id: UUID) -> Decimal:
    return db.scalar(
        select(func.coalesce(func.sum(Conta.valor_pago), 0)).where(
            Conta.caixa_id == caixa_id, Conta.status == "paga"
        )
    )


# --- Fluxo de caixa ---

def fluxo(db: Session, inicio: date, fim: date, loja_id: UUID | None) -> FluxoCaixa:
    if fim < inicio:
        raise ErroDeNegocio("A data final é antes da inicial")
    if (fim - inicio).days > 366:
        raise ErroDeNegocio("Escolha um período de até um ano")

    dias: dict[date, dict[str, Decimal]] = defaultdict(lambda: defaultdict(lambda: ZERO))

    # O que entrou no caixa pelas vendas: tudo menos a parte a prazo, e o troco sai do dinheiro.
    dia_venda = cast(func.timezone(FUSO.key, Venda.finalizada_em), Date)
    vendas = (
        select(dia_venda.label("dia"), func.sum(VendaPagamento.valor).label("valor"))
        .join(VendaPagamento, VendaPagamento.venda_id == Venda.id)
        .where(Venda.status == "finalizada", VendaPagamento.forma.not_in(("prazo", "convenio")), dia_venda.between(inicio, fim))
        .group_by(dia_venda)
    )
    trocos = (
        select(dia_venda.label("dia"), func.sum(Venda.troco).label("valor"))
        .where(Venda.status == "finalizada", dia_venda.between(inicio, fim))
        .group_by(dia_venda)
    )
    if loja_id:
        da_loja = Venda.caixa_id.in_(select(Caixa.id).where(Caixa.loja_id == loja_id))
        vendas, trocos = vendas.where(da_loja), trocos.where(da_loja)
    for dia, valor in db.execute(vendas):
        dias[dia]["vendas"] += valor
    for dia, valor in db.execute(trocos):
        dias[dia]["vendas"] -= valor

    contas = select(Conta).where(Conta.status != "cancelada")
    if loja_id:
        contas = contas.where(Conta.loja_id == loja_id)
    pagas = db.scalars(contas.where(Conta.status == "paga", Conta.pago_em.between(inicio, fim))).all()
    for conta in pagas:
        dias[conta.pago_em]["recebimentos" if conta.tipo == "receber" else "pagamentos"] += conta.valor_pago
    abertas = db.scalars(contas.where(Conta.status == "aberta", Conta.vencimento <= fim)).all()
    vencido = {"receber": ZERO, "pagar": ZERO}
    for conta in abertas:
        if conta.vencimento < inicio:
            vencido[conta.tipo] += conta.valor
        else:
            dias[conta.vencimento][f"previsto_{conta.tipo}"] += conta.valor

    lista = []
    acumulado = entradas = saidas = ZERO
    dia = inicio
    while dia <= fim:
        d = dias[dia]
        entrada = d["vendas"] + d["recebimentos"] + d["previsto_receber"]
        saida_dia = d["pagamentos"] + d["previsto_pagar"]
        entradas += entrada
        saidas += saida_dia
        acumulado += entrada - saida_dia
        lista.append(
            DiaFluxo(
                data=dia,
                vendas=d["vendas"],
                recebimentos=d["recebimentos"],
                pagamentos=d["pagamentos"],
                previsto_receber=d["previsto_receber"],
                previsto_pagar=d["previsto_pagar"],
                saldo=entrada - saida_dia,
                acumulado=acumulado,
            )
        )
        dia += timedelta(days=1)

    return FluxoCaixa(
        inicio=inicio,
        fim=fim,
        dias=lista,
        entradas=entradas,
        saidas=saidas,
        resultado=entradas - saidas,
        vencido_receber=vencido["receber"],
        vencido_pagar=vencido["pagar"],
    )
