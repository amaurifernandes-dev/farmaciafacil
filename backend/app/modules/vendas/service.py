from collections import defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import TokenDados
from app.modules.auth.models import Usuario
from app.modules.estoque.models import MovimentoEstoque
from app.modules.estoque.service import Referencia, baixar_fefo, devolver_movimento, saldo_vendavel
from app.modules.clientes.models import Cliente
from app.modules.controlados.models import Receita
from app.modules.devolucoes.integracao import devolvido_no_caixa, estornar_vales, normalizar_codigo, tem_devolucao, usar_vales
from app.modules.convenios.service import cancelar_da_venda as cancelar_compra_convenio
from app.modules.convenios.service import desconto_do_cliente as desconto_do_convenio
from app.modules.convenios.service import lancar_compra as lancar_compra_convenio
from app.modules.controlados.regras import receituario_da_venda, validar_quantidade, validar_receita
from app.modules.farmacias.models import Farmacia
from app.modules.faltas.service import entregar_da_venda, estornar_da_venda as reabrir_encomendas
from app.modules.fidelidade.service import desconto_do_resgate, estornar_da_venda, pontuar_venda
from app.modules.financeiro.service import cancelar_fiado_da_venda, lancar_fiado, recebido_no_caixa
from app.modules.lojas.models import Loja, Terminal
from app.modules.lojas.service import matriz, obter_loja, pode_receber
from app.modules.pedidos.models import EM_ANDAMENTO, Pedido
from app.modules.popular import service as popular
from app.modules.produtos.models import Produto
from app.modules.servicos.service import recebido_no_caixa as servicos_no_caixa
from app.modules.promocoes.models import Promocao
from app.modules.promocoes.service import melhor, vigentes_por_produto
from app.modules.vendas.models import Caixa, PreVenda, Venda, VendaItem, VendaPagamento
from app.modules.vendas.schemas import CaixaSaida, PreVendaCriar, PreVendaSaida, ResumoCaixa, VendaCriar
from app.shared.datas import hoje
from app.shared.erros import Conflito, ErroDeNegocio, NaoEncontrado, SemPermissao

CENTAVO = Decimal("0.01")
GERENTES = ("admin", "gerente")
OPERADORES = ("admin", "gerente", "farmaceutico", "caixa")


def _agora() -> datetime:
    return datetime.now(timezone.utc)


# --- Caixa ---

def caixa_do_terminal(db: Session, terminal: Terminal) -> Caixa | None:
    return db.scalar(select(Caixa).where(Caixa.terminal_id == terminal.id, Caixa.status == "aberto"))


def caixa_do_usuario(db: Session, usuario_id: UUID) -> Caixa | None:
    return db.scalar(select(Caixa).where(Caixa.usuario_id == usuario_id, Caixa.status == "aberto"))


def _exigir_terminal(terminal: Terminal | None) -> Terminal:
    if terminal is None:
        raise ErroDeNegocio(
            "Este computador não está registrado como PDV. Peça a um gerente para registrá-lo em Caixas."
        )
    return terminal


def abrir_caixa(db: Session, usuario: TokenDados, terminal: Terminal | None, valor_abertura: Decimal) -> Caixa:
    terminal = _exigir_terminal(terminal)
    if usuario.papel not in OPERADORES:
        raise SemPermissao("Seu perfil não pode abrir caixa")
    loja = db.get(Loja, terminal.loja_id)
    motivo = pode_receber(loja, terminal)
    if motivo:
        raise ErroDeNegocio(motivo)
    if caixa_do_terminal(db, terminal) is not None:
        raise Conflito(f"O {terminal.nome} já tem um caixa aberto")
    if caixa_do_usuario(db, usuario.usuario_id) is not None:
        raise Conflito("Você já tem um caixa aberto em outro PDV. Feche-o antes de abrir este.")
    caixa = Caixa(
        usuario_id=usuario.usuario_id,
        terminal_id=terminal.id,
        loja_id=loja.id,
        valor_abertura=valor_abertura,
        aberto_em=_agora(),
    )
    db.add(caixa)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise Conflito("Este PDV ou este operador já tem um caixa aberto")
    return caixa


def caixa_para_vender(db: Session, usuario: TokenDados, terminal: Terminal | None) -> Caixa:
    """O caixa aberto deste PDV, desde que o operador possa usá-lo."""
    terminal = _exigir_terminal(terminal)
    caixa = caixa_do_terminal(db, terminal)
    if caixa is None:
        raise ErroDeNegocio("Abra o caixa antes de vender")
    if caixa.usuario_id != usuario.usuario_id and usuario.papel not in GERENTES:
        raise SemPermissao("Este caixa foi aberto por outro operador. Feche-o antes de abrir o seu.")
    return caixa


def obter_caixa(db: Session, caixa_id: UUID) -> Caixa:
    caixa = db.get(Caixa, caixa_id)
    if caixa is None:
        raise NaoEncontrado("Caixa não encontrado")
    return caixa


def listar_caixas(db: Session, status: str | None, pagina: int, por_pagina: int) -> list[ResumoCaixa]:
    filtro = select(Caixa)
    if status:
        filtro = filtro.where(Caixa.status == status)
    caixas = db.scalars(
        filtro.order_by(Caixa.aberto_em.desc()).offset((pagina - 1) * por_pagina).limit(por_pagina)
    ).all()
    return [resumo_caixa(db, caixa) for caixa in caixas]


def resumo_caixa(db: Session, caixa: Caixa) -> ResumoCaixa:
    finalizadas = select(Venda.id).where(Venda.caixa_id == caixa.id, Venda.status == "finalizada")
    quantidade, total, troco = db.execute(
        select(func.count(), func.coalesce(func.sum(Venda.total), 0), func.coalesce(func.sum(Venda.troco), 0))
        .where(Venda.id.in_(finalizadas))
    ).one()
    por_forma = dict(
        db.execute(
            select(VendaPagamento.forma, func.sum(VendaPagamento.valor))
            .where(VendaPagamento.venda_id.in_(finalizadas))
            .group_by(VendaPagamento.forma)
        ).all()
    )
    # Fiado recebido em dinheiro neste caixa também está na gaveta.
    recebimentos = recebido_no_caixa(db, caixa.id)
    # E o dinheiro dos serviços farmacêuticos (pressão, glicemia, injetáveis).
    servicos = servicos_no_caixa(db, caixa.id)
    # E sai o dinheiro devolvido a clientes nas trocas.
    devolucoes = devolvido_no_caixa(db, caixa.id)
    esperado = (
        caixa.valor_abertura + por_forma.get("dinheiro", Decimal(0)) - troco + recebimentos + servicos - devolucoes
    )
    diferenca = None
    if caixa.valor_fechamento_informado is not None:
        diferenca = caixa.valor_fechamento_informado - esperado
    terminal = db.get(Terminal, caixa.terminal_id) if caixa.terminal_id else None
    loja = db.get(Loja, caixa.loja_id) if caixa.loja_id else None
    return ResumoCaixa(
        caixa=CaixaSaida.model_validate(caixa),
        operador=db.get(Usuario, caixa.usuario_id).nome,
        terminal=terminal.nome if terminal else None,
        loja=loja.nome if loja else None,
        quantidade_vendas=quantidade,
        total_vendido=total,
        por_forma=por_forma,
        recebimentos_dinheiro=recebimentos,
        servicos_dinheiro=servicos,
        devolucoes_dinheiro=devolucoes,
        dinheiro_esperado=esperado,
        diferenca=diferenca,
    )


def fechar_caixa(db: Session, usuario: TokenDados, caixa_id: UUID, valor_informado: Decimal) -> ResumoCaixa:
    caixa = obter_caixa(db, caixa_id)
    if caixa.usuario_id != usuario.usuario_id and usuario.papel not in GERENTES:
        raise SemPermissao("Só o próprio operador ou um gerente pode fechar este caixa")
    if caixa.status != "aberto":
        raise Conflito("Este caixa já está fechado")
    caixa.status = "fechado"
    caixa.fechado_em = _agora()
    caixa.valor_fechamento_informado = valor_informado
    resumo = resumo_caixa(db, caixa)
    db.commit()
    return resumo


# --- Venda ---

def _proximo_numero(db: Session) -> int:
    # Trava por farmácia durante a transação, para dois caixas não pegarem o mesmo número.
    db.execute(text("SELECT pg_advisory_xact_lock(hashtext(current_setting('app.farmacia_id')))"))
    return db.scalar(select(func.coalesce(func.max(Venda.numero), 0) + 1))


def _venda_pela_chave(db: Session, chave: UUID) -> Venda | None:
    return db.scalar(select(Venda).where(Venda.chave_idempotencia == chave))


def registrar_venda(
    db: Session, usuario: TokenDados, terminal: Terminal | None, dados: VendaCriar
) -> tuple[Venda, bool]:
    """Grava a venda, baixa o estoque e registra os pagamentos numa transação só.

    Devolve (venda, criada). Se a chave já foi usada, devolve a venda existente e criada=False.
    """
    existente = _venda_pela_chave(db, dados.chave_idempotencia)
    if existente is not None:
        return existente, False

    offline = dados.offline_em is not None
    caixa = _caixa_da_venda_offline(db, usuario, terminal, dados) if offline else caixa_para_vender(db, usuario, terminal)
    pre_venda = _pre_venda_para_receber(db, dados.pre_venda_id) if dados.pre_venda_id else None

    if dados.cliente_id is not None and db.get(Cliente, dados.cliente_id) is None:
        raise NaoEncontrado("Cliente não encontrado")
    venda = Venda(
        caixa_id=caixa.id,
        usuario_id=usuario.usuario_id,
        # Venda que veio de pré-venda é do balconista que atendeu.
        vendedor_id=pre_venda.usuario_id if pre_venda is not None else usuario.usuario_id,
        chave_idempotencia=dados.chave_idempotencia,
        cliente_cpf=dados.cliente_cpf,
        cliente_id=dados.cliente_id,
        finalizada_em=dados.offline_em if offline else _agora(),
        offline=offline,
        entrega=False,
        taxa_entrega=Decimal(0),
    )

    # Caixas antigos, de antes das lojas, vendem do estoque da matriz.
    loja_id = caixa.loja_id or matriz(db).id
    promocoes = vigentes_por_produto(db, [i.produto_id for i in dados.itens], loja_id)
    farmacia = db.get(Farmacia, usuario.farmacia_id)

    subtotal = Decimal(0)
    descontos = dados.desconto
    manuais = dados.desconto  # só o desconto dado pelo operador conta no limite do caixa
    vendidos = []
    for ordem, entrada in enumerate(dados.itens, start=1):
        produto = db.get(Produto, entrada.produto_id)
        # A venda offline já aconteceu no balcão: aceita mesmo se o produto foi desativado depois.
        if produto is None or (not produto.ativo and not offline):
            raise NaoEncontrado("Produto não encontrado")
        validar_quantidade(produto, entrada.quantidade)
        vendidos.append(produto)
        if offline and entrada.preco_unitario is not None:
            # Vale o preço e a promoção da cópia do catálogo que o caixa tinha na hora.
            preco = entrada.preco_unitario
            desconto_promocao = entrada.desconto_promocao or Decimal(0)
            promocao = db.get(Promocao, entrada.promocao_id) if entrada.promocao_id and desconto_promocao else None
        else:
            preco = produto.preco_venda
            promocao, desconto_promocao = melhor(
                promocoes.get(produto.id, []), produto.preco_venda, entrada.quantidade, dados.cliente_id is not None
            )
        bruto = (preco * entrada.quantidade).quantize(CENTAVO)
        if entrada.desconto + desconto_promocao > bruto:
            raise ErroDeNegocio(f"Desconto maior que o valor de {produto.nome}")
        desconto_item = entrada.desconto + desconto_promocao
        venda.itens.append(
            VendaItem(
                ordem=ordem,
                produto_id=produto.id,
                descricao=produto.nome if not produto.apresentacao else f"{produto.nome} {produto.apresentacao}",
                quantidade=entrada.quantidade,
                preco_unitario=preco,
                desconto=desconto_item,
                total=bruto - desconto_item,
                custo_unitario=produto.preco_custo,
                promocao_id=promocao.id if promocao else None,
                desconto_promocao=desconto_promocao,
                comissao=produto.comissao if produto.comissao is not None else farmacia.comissao_padrao,
            )
        )
        subtotal += bruto
        descontos += desconto_item
        manuais += entrada.desconto

    if descontos > subtotal:
        raise ErroDeNegocio("Desconto maior que o valor da venda")
    receituario = receituario_da_venda(vendidos)
    if receituario is not None:
        validar_receita(receituario, dados.receita, hoje())
    maximo = farmacia.desconto_maximo_caixa
    # Offline o caixa já conferiu o limite com a cópia das configurações; a venda já aconteceu.
    if not offline and usuario.papel not in GERENTES and subtotal > 0 and manuais * 100 / subtotal > maximo:
        raise SemPermissao(f"Desconto acima de {maximo:g}% precisa de um gerente")

    # Funcionário de empresa conveniada ganha o desconto da empresa (fora do limite do caixa).
    desconto_convenio = (
        Decimal(0) if offline else desconto_do_convenio(db, dados.cliente_id, subtotal - (descontos - dados.desconto))
    )
    if desconto_convenio:
        if descontos + desconto_convenio > subtotal:
            raise ErroDeNegocio("Com o desconto do convênio, o desconto passa do valor da venda")
        venda.desconto_convenio = desconto_convenio
        descontos += desconto_convenio

    # A troca de pontos vira desconto, mas não conta no limite de desconto do caixa.
    if dados.pontos_resgatados:
        desconto_pontos = desconto_do_resgate(db, farmacia, dados.cliente_id, dados.pontos_resgatados)
        if descontos + desconto_pontos > subtotal:
            raise ErroDeNegocio("Os pontos valem mais que o restante da compra. Use menos pontos.")
        venda.pontos_resgatados = dados.pontos_resgatados
        venda.desconto_pontos = desconto_pontos
        descontos += desconto_pontos

    venda.subtotal = subtotal
    venda.desconto = descontos
    # A taxa de entrega vem do pedido (pela pré-venda), nunca do navegador.
    if pre_venda is not None:
        venda.entrega = pre_venda.entrega
        venda.taxa_entrega = pre_venda.taxa_entrega
    venda.total = subtotal - descontos + venda.taxa_entrega

    # Farmácia Popular: o governo paga parte dos remédios do programa; o paciente paga o resto.
    governo, itens_popular = popular.preparar(
        db, farmacia, dados.popular, venda.itens, vendidos,
        sum((p.valor for p in dados.pagamentos if p.forma == "popular"), Decimal(0)), hoje(),
    )
    if governo > venda.total:
        raise ErroDeNegocio("Com os descontos, a venda ficou menor que a parte do governo. Tire o desconto.")
    if dados.popular is not None and not venda.cliente_cpf:
        venda.cliente_cpf = dados.popular.paciente_cpf  # vai na nota

    pago = sum((p.valor for p in dados.pagamentos), Decimal(0))
    em_dinheiro = sum((p.valor for p in dados.pagamentos if p.forma == "dinheiro"), Decimal(0))
    if pago < venda.total:
        raise ErroDeNegocio(f"Faltam R$ {venda.total - pago:.2f} para fechar a venda")
    troco = pago - venda.total
    if troco > em_dinheiro:
        raise ErroDeNegocio("Troco só pode sair do pagamento em dinheiro")
    venda.troco = troco
    # Vale-troca: confere e desconta o saldo (trava o vale até o fim da venda).
    vales = usar_vales(db, dados.pagamentos)
    venda.pagamentos = [
        VendaPagamento(
            forma=p.forma, valor=p.valor, vale_id=vales[normalizar_codigo(p.vale_codigo)] if p.forma == "vale" else None
        )
        for p in dados.pagamentos
    ]

    if offline:
        _anotar_sem_estoque(db, loja_id, venda)
    venda.numero = _proximo_numero(db)
    db.add(venda)
    db.flush()  # gera os ids dos itens para referenciar nos movimentos
    if receituario is not None:
        db.add(_receita(venda, dados.receita))

    for item in venda.itens:
        produto = db.get(Produto, item.produto_id)
        baixar_fefo(
            db, loja_id, produto, item.quantidade, usuario.usuario_id, Referencia("venda_item", item.id),
            permitir_faltar=offline,
        )

    if governo:
        popular.lancar(db, venda, loja_id, dados.popular, governo, itens_popular, hoje())
    no_convenio = sum((p.valor for p in dados.pagamentos if p.forma == "convenio"), Decimal(0))
    if no_convenio:
        lancar_compra_convenio(db, venda, loja_id, no_convenio)
    a_prazo = [p for p in dados.pagamentos if p.forma == "prazo"]
    if a_prazo:
        valor = sum((p.valor for p in a_prazo), Decimal(0))
        vencimento = next((p.vencimento for p in a_prazo if p.vencimento), None)
        lancar_fiado(db, usuario.usuario_id, venda, loja_id, valor, vencimento, farmacia.dias_prazo_padrao)
    pontuar_venda(db, farmacia, usuario.usuario_id, venda)
    entregar_da_venda(db, venda)

    if pre_venda is not None:
        pre_venda.status = "recebida"
        # Pedido do site ou do WhatsApp: pago no caixa, está entregue.
        db.execute(
            update(Pedido)
            .where(Pedido.pre_venda_id == pre_venda.id, Pedido.status.in_(EM_ANDAMENTO))
            .values(status="entregue")
        )
        pre_venda.venda_id = venda.id
        pre_venda.finalizada_em = venda.finalizada_em

    try:
        db.commit()
    except IntegrityError:
        # Outro envio com a mesma chave chegou junto: devolve o que foi gravado por ele.
        db.rollback()
        existente = _venda_pela_chave(db, dados.chave_idempotencia)
        if existente is None:
            raise
        return existente, False
    return venda, True


# Formas que dependem de conferir algo no servidor na hora (limite, saldo, autorização).
FORMAS_SO_ONLINE = ("prazo", "convenio", "popular", "vale")
OFFLINE_MAXIMO = timedelta(days=7)


def _caixa_da_venda_offline(db: Session, usuario: TokenDados, terminal: Terminal | None, dados: VendaCriar) -> Caixa:
    """Confere a venda feita sem internet e devolve o caixa em que ela aconteceu."""
    agora = _agora()
    if dados.offline_em > agora + timedelta(minutes=10):
        raise ErroDeNegocio("A hora da venda offline está no futuro. Confira o relógio deste computador.")
    if dados.offline_em < agora - OFFLINE_MAXIMO:
        raise ErroDeNegocio("Venda offline com mais de 7 dias. Peça a um gerente para lançar à mão.")
    if any(p.forma in FORMAS_SO_ONLINE for p in dados.pagamentos):
        raise ErroDeNegocio("Sem internet, o caixa só recebe em dinheiro, cartão ou Pix")
    if dados.pontos_resgatados or dados.pre_venda_id or dados.popular:
        raise ErroDeNegocio("Pontos, pré-venda e Farmácia Popular precisam de internet na hora da venda")
    terminal = _exigir_terminal(terminal)
    caixa = db.get(Caixa, dados.caixa_id) if dados.caixa_id else caixa_do_terminal(db, terminal)
    if caixa is None:
        raise NaoEncontrado("O caixa desta venda offline não foi encontrado")
    if caixa.terminal_id != terminal.id:
        raise ErroDeNegocio("Esta venda offline é de outro PDV. Envie pelo computador em que ela foi feita.")
    if caixa.usuario_id != usuario.usuario_id and usuario.papel not in GERENTES:
        raise SemPermissao("Esta venda offline foi feita no caixa de outro operador")
    return caixa


def _anotar_sem_estoque(db: Session, loja_id: UUID, venda: Venda) -> None:
    """Offline pode ter vendido mais do que o sistema tinha: o estoque zera e a diferença fica anotada."""
    restante: dict[UUID, Decimal] = {}
    for item in venda.itens:
        if item.produto_id not in restante:
            restante[item.produto_id] = saldo_vendavel(db, item.produto_id, loja_id)
        tem = max(restante[item.produto_id], Decimal(0))
        item.sem_estoque = max(item.quantidade - tem, Decimal(0))
        restante[item.produto_id] = tem - item.quantidade


def _receita(venda: Venda, dados) -> Receita:
    valores = dados.model_dump()
    if valores["comprador_documento"] and valores["comprador_tipo_documento"] is None:
        valores["comprador_tipo_documento"] = 2  # carteira de identidade (RG)
    if valores["paciente_idade"] is None:
        valores["paciente_unidade_idade"] = None
    return Receita(venda_id=venda.id, uso=2 if dados.prescritor_conselho == "CRMV" else 1, **valores)


def obter_venda(db: Session, venda_id: UUID) -> Venda:
    venda = db.get(Venda, venda_id)
    if venda is None:
        raise NaoEncontrado("Venda não encontrada")
    return venda


def listar_vendas(db: Session, caixa_id: UUID | None, pagina: int, por_pagina: int) -> list[Venda]:
    filtro = select(Venda)
    if caixa_id is not None:
        filtro = filtro.where(Venda.caixa_id == caixa_id)
    return db.scalars(
        filtro.order_by(Venda.numero.desc()).offset((pagina - 1) * por_pagina).limit(por_pagina)
    ).all()


def cancelar_venda(db: Session, usuario: TokenDados, venda_id: UUID, motivo: str) -> Venda:
    venda = db.scalar(select(Venda).where(Venda.id == venda_id).with_for_update(of=Venda))
    if venda is None:
        raise NaoEncontrado("Venda não encontrada")
    if venda.status == "cancelada":
        raise Conflito("Esta venda já foi cancelada")
    if tem_devolucao(db, venda.id):
        raise Conflito("Esta venda já teve itens devolvidos e não pode mais ser cancelada. Devolva os outros itens.")

    # Devolve a cada lote exatamente o que saiu dele.
    movimentos = db.scalars(
        select(MovimentoEstoque).where(
            MovimentoEstoque.referencia_tipo == "venda_item",
            MovimentoEstoque.referencia_id.in_([item.id for item in venda.itens]),
        )
    ).all()
    cancelar_fiado_da_venda(db, venda)
    cancelar_compra_convenio(db, venda)
    popular.cancelar_da_venda(db, venda)
    estornar_da_venda(db, usuario.usuario_id, venda)
    reabrir_encomendas(db, venda)
    estornar_vales(db, venda)
    for movimento in movimentos:
        devolver_movimento(db, movimento, usuario.usuario_id, motivo=f"Cancelamento da venda {venda.numero}")

    venda.status = "cancelada"
    venda.cancelada_em = _agora()
    venda.motivo_cancelamento = motivo
    db.commit()
    return venda


# --- Pré-venda ---

def _descricao(produto: Produto) -> str:
    return produto.nome if not produto.apresentacao else f"{produto.nome} {produto.apresentacao}"


def criar_pre_venda(
    db: Session,
    usuario: TokenDados,
    terminal: Terminal | None,
    dados: PreVendaCriar,
    entrega: bool = False,
    taxa_entrega: Decimal = Decimal(0),
    pago_antecipado: Decimal = Decimal(0),
) -> PreVenda:
    """Pré-venda do balcão, ou de um pedido (com a taxa de entrega e o Pix já pago, se houver)."""
    if dados.loja_id is not None:
        loja = obter_loja(db, dados.loja_id)
    elif terminal is not None:
        loja = db.get(Loja, terminal.loja_id)
    else:
        loja = matriz(db)

    itens = []
    total = Decimal(0)
    for entrada in dados.itens:
        produto = db.get(Produto, entrada.produto_id)
        if produto is None or not produto.ativo:
            raise NaoEncontrado("Produto não encontrado")
        valor = (produto.preco_venda * entrada.quantidade).quantize(CENTAVO)
        itens.append(
            {
                "produto_id": str(produto.id),
                "ean": produto.ean,
                "descricao": _descricao(produto),
                "quantidade": str(entrada.quantidade),
                "preco_unitario": str(produto.preco_venda),
                "total": str(valor),
            }
        )
        total += valor

    # Trava separada da numeração de vendas.
    db.execute(text("SELECT pg_advisory_xact_lock(hashtext('pre_venda:' || current_setting('app.farmacia_id')))"))
    numero = db.scalar(select(func.coalesce(func.max(PreVenda.numero), 0) + 1))
    pre_venda = PreVenda(
        loja_id=loja.id,
        numero=numero,
        usuario_id=usuario.usuario_id,
        itens=itens,
        total=total + taxa_entrega,
        cliente_cpf=dados.cliente_cpf,
        entrega=entrega,
        taxa_entrega=taxa_entrega,
        pago_antecipado=pago_antecipado,
    )
    db.add(pre_venda)
    db.commit()
    return pre_venda


def saida_pre_venda(db: Session, pre_venda: PreVenda) -> PreVendaSaida:
    return PreVendaSaida.model_validate(
        {
            **{c: getattr(pre_venda, c) for c in PreVendaSaida.model_fields if c != "vendedor"},
            "vendedor": db.get(Usuario, pre_venda.usuario_id).nome,
        }
    )


def listar_pre_vendas(db: Session, status: str | None, loja_id: UUID | None) -> list[PreVenda]:
    filtro = select(PreVenda)
    if status:
        filtro = filtro.where(PreVenda.status == status)
    if loja_id:
        filtro = filtro.where(PreVenda.loja_id == loja_id)
    return db.scalars(filtro.order_by(PreVenda.numero.desc()).limit(100)).all()


def obter_pre_venda(db: Session, pre_venda_id: UUID) -> PreVenda:
    pre_venda = db.get(PreVenda, pre_venda_id)
    if pre_venda is None:
        raise NaoEncontrado("Pré-venda não encontrada")
    return pre_venda


def pre_venda_pelo_numero(db: Session, numero: int) -> PreVenda:
    pre_venda = db.scalar(select(PreVenda).where(PreVenda.numero == numero))
    if pre_venda is None:
        raise NaoEncontrado(f"Pré-venda nº {numero} não encontrada")
    return pre_venda


def _pre_venda_para_receber(db: Session, pre_venda_id: UUID) -> PreVenda:
    pre_venda = db.scalar(select(PreVenda).where(PreVenda.id == pre_venda_id).with_for_update())
    if pre_venda is None:
        raise NaoEncontrado("Pré-venda não encontrada")
    if pre_venda.status != "aberta":
        raise Conflito(f"A pré-venda nº {pre_venda.numero} já foi {pre_venda.status}")
    return pre_venda


def cancelar_pre_venda(db: Session, pre_venda_id: UUID) -> PreVenda:
    pre_venda = _pre_venda_para_receber(db, pre_venda_id)
    pre_venda.status = "cancelada"
    pre_venda.finalizada_em = _agora()
    db.commit()
    return pre_venda
