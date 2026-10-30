from datetime import datetime, timezone
from decimal import ROUND_DOWN, Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.fiscal.models import ConfiguracaoFiscal, NotaFiscal
from app.modules.fiscal.provedores import ErroDeConfiguracao, ProvedorFiscal, ResultadoNota
from app.modules.fiscal.schemas import ConfiguracaoFiscalDados
from app.modules.lojas.models import Loja
from app.modules.produtos.models import Produto
from app.modules.vendas.models import Caixa, Venda
from app.shared.datas import FUSO
from app.shared.erros import Conflito, ErroDeNegocio, NaoEncontrado

CENTAVO = Decimal("0.01")
# Código tPag da NFC-e para cada forma de pagamento do PDV.
FORMA_PAGAMENTO = {"dinheiro": "01", "credito": "03", "debito": "04", "pix": "17"}
# A SEFAZ só aceita cancelar a NFC-e com justificativa de 15 a 255 caracteres.
JUSTIFICATIVA_MINIMA = 15


def _agora() -> datetime:
    return datetime.now(timezone.utc)


# --- Configuração ---

def obter_configuracao(db: Session) -> ConfiguracaoFiscal | None:
    return db.scalar(select(ConfiguracaoFiscal))


def salvar_configuracao(db: Session, dados: ConfiguracaoFiscalDados) -> ConfiguracaoFiscal:
    config = obter_configuracao(db)
    if config is None:
        config = ConfiguracaoFiscal()
        db.add(config)
    for campo, valor in dados.model_dump().items():
        setattr(config, campo, valor)
    db.commit()
    return config


# --- Montagem da NFC-e ---

def _ratear(total: Decimal, pesos: list[Decimal]) -> list[Decimal]:
    """Divide o desconto da venda entre os itens, proporcional ao valor; a sobra de centavos vai para o último."""
    base = sum(pesos, Decimal(0))
    if total == 0 or base == 0:
        return [Decimal(0)] * len(pesos)
    partes = [(total * peso / base).quantize(CENTAVO, rounding=ROUND_DOWN) for peso in pesos]
    partes[-1] += total - sum(partes, Decimal(0))
    return partes


def loja_emitente(db: Session, venda: Venda) -> Loja:
    """A NFC-e sai pelo CNPJ da loja do caixa. Caixas antigos, sem loja, usam a matriz."""
    caixa = db.get(Caixa, venda.caixa_id)
    if caixa is not None and caixa.loja_id is not None:
        return db.get(Loja, caixa.loja_id)
    loja = db.scalar(select(Loja).where(Loja.matriz.is_(True)))
    if loja is None:
        raise ErroDeNegocio("Cadastre a loja matriz antes de emitir NFC-e")
    return loja


def montar_nfce(venda: Venda, loja: Loja, config: ConfiguracaoFiscal, produtos: dict) -> dict:
    """Converte a venda no JSON de NFC-e da Focus NFe. Levanta ErroDeNegocio se faltar dado fiscal."""
    sem_ncm = [item.descricao for item in venda.itens if not produtos[item.produto_id].ncm]
    if sem_ncm:
        raise ErroDeNegocio(f"Produto sem NCM cadastrado: {', '.join(sem_ncm)}")

    desconto_da_venda = venda.desconto - sum((item.desconto for item in venda.itens), Decimal(0))
    rateio = _ratear(desconto_da_venda, [item.total for item in venda.itens])

    itens = []
    for item, desconto_rateado in zip(venda.itens, rateio):
        produto: Produto = produtos[item.produto_id]
        quantidade = f"{item.quantidade:.4f}"
        desconto = item.desconto + desconto_rateado
        pis_cofins = produto.pis_cofins_situacao_tributaria or config.pis_cofins_situacao_tributaria_padrao
        dados = {
            "numero_item": str(item.ordem),
            "codigo_produto": produto.ean or str(produto.id)[:60],
            "descricao": item.descricao[:120],
            "codigo_ncm": produto.ncm,
            "cfop": produto.cfop or config.cfop_padrao,
            "unidade_comercial": produto.unidade,
            "unidade_tributavel": produto.unidade,
            "quantidade_comercial": quantidade,
            "quantidade_tributavel": quantidade,
            "valor_unitario_comercial": str(item.preco_unitario),
            "valor_unitario_tributavel": str(item.preco_unitario),
            "valor_bruto": str(item.total + item.desconto),
            "codigo_barras_comercial": produto.ean or "SEM GTIN",
            "codigo_barras_tributavel": produto.ean or "SEM GTIN",
            "icms_origem": produto.icms_origem,
            "icms_situacao_tributaria": produto.icms_situacao_tributaria or config.icms_situacao_tributaria_padrao,
            "pis_situacao_tributaria": pis_cofins,
            "cofins_situacao_tributaria": pis_cofins,
        }
        if desconto > 0:
            dados["valor_desconto"] = str(desconto)
        if produto.cest:
            dados["cest"] = produto.cest
        itens.append(dados)

    # O troco sai do dinheiro, então o dinheiro entra na nota já descontado dele.
    pagamentos: dict[str, Decimal] = {}
    for pagamento in venda.pagamentos:
        pagamentos[pagamento.forma] = pagamentos.get(pagamento.forma, Decimal(0)) + pagamento.valor
    if "dinheiro" in pagamentos:
        pagamentos["dinheiro"] -= venda.troco
    formas = []
    for forma, valor in pagamentos.items():
        if valor <= 0:
            continue
        dados = {"forma_pagamento": FORMA_PAGAMENTO[forma], "valor_pagamento": str(valor)}
        if forma != "dinheiro":
            dados["tipo_integracao"] = "2"  # maquininha não integrada ao PDV
        formas.append(dados)
    if not formas:
        # Venda de valor zero (100% de desconto): a NFC-e exige uma forma, usa "sem pagamento".
        formas.append({"forma_pagamento": "90", "valor_pagamento": "0.00"})

    nota = {
        "cnpj_emitente": loja.cnpj,
        "data_emissao": datetime.now(FUSO).isoformat(timespec="seconds"),
        "natureza_operacao": "VENDA AO CONSUMIDOR",
        "presenca_comprador": "1",
        "modalidade_frete": "9",
        "local_destino": "1",
        "indicador_inscricao_estadual_destinatario": "9",
        "items": itens,
        "formas_pagamento": formas,
    }
    if venda.cliente_cpf:
        nota["cpf_destinatario"] = venda.cliente_cpf
    return nota


# --- Emissão ---

def _aplicar(nota: NotaFiscal, resultado: ResultadoNota) -> None:
    nota.status = resultado.status
    nota.mensagem = (resultado.mensagem or "")[:500] or None
    for campo in ("status_sefaz", "numero", "serie", "chave", "url_xml", "url_danfe", "url_qrcode",
                  "url_consulta", "url_xml_cancelamento"):
        valor = getattr(resultado, campo)
        if valor is not None:
            setattr(nota, campo, valor)
    if resultado.status == "autorizada" and nota.autorizada_em is None:
        nota.autorizada_em = _agora()
    if resultado.status == "cancelada" and nota.cancelada_em is None:
        nota.cancelada_em = _agora()


def nota_da_venda(db: Session, venda_id) -> NotaFiscal | None:
    return db.scalar(select(NotaFiscal).where(NotaFiscal.venda_id == venda_id))


def emitir_nfce(db: Session, provedor: ProvedorFiscal | None, venda: Venda) -> NotaFiscal:
    """Emite (ou reenvia) a NFC-e da venda. Nunca levanta por falha do provedor: o resultado fica na nota."""
    if provedor is None:
        raise ErroDeNegocio("Emissão de NFC-e desligada neste servidor")
    config = obter_configuracao(db)
    if config is None:
        raise ErroDeNegocio("Configure os dados fiscais da farmácia antes de emitir NFC-e")
    if venda.status == "cancelada":
        raise Conflito("Venda cancelada não emite NFC-e")

    nota = db.scalar(select(NotaFiscal).where(NotaFiscal.venda_id == venda.id).with_for_update())
    if nota is not None and nota.status in ("autorizada", "cancelada"):
        return nota
    if nota is None:
        nota = NotaFiscal(venda_id=venda.id, ambiente=config.ambiente, status="erro")
        db.add(nota)
        db.flush()
    ref = str(venda.id)

    try:
        if nota.status == "processando":
            # A tentativa anterior pode ter chegado à SEFAZ: consulta antes de reenviar.
            resultado = provedor.consultar(nota.ambiente, ref)
            if resultado.status in ("autorizada", "cancelada"):
                _aplicar(nota, resultado)
                db.commit()
                return nota
            if resultado.status in ("processando", "erro"):
                # Continua sem saber se chegou; não reenvia para não arriscar a mesma venda em duas notas.
                nota.mensagem = resultado.mensagem
                db.commit()
                return nota
            # Rejeitada ou não encontrada: pode enviar de novo com a mesma referência.
        produtos = {p.id: p for p in db.scalars(select(Produto).where(Produto.id.in_([i.produto_id for i in venda.itens])))}
        try:
            dados = montar_nfce(venda, loja_emitente(db, venda), config, produtos)
        except ErroDeNegocio as erro:
            resultado = ResultadoNota(status="erro", mensagem=erro.mensagem)
        else:
            nota.tentativas += 1
            resultado = provedor.emitir(nota.ambiente, ref, dados)
    except ErroDeConfiguracao as erro:
        resultado = ResultadoNota(status="erro", mensagem=str(erro))
    _aplicar(nota, resultado)
    db.commit()
    db.expire(venda, ["nota"])
    return nota


def emitir_apos_venda(db: Session, provedor: ProvedorFiscal | None, venda: Venda) -> NotaFiscal | None:
    """Chamado logo depois de gravar a venda. A venda já está salva; se a nota falhar, dá para reenviar."""
    if provedor is None:
        return None
    config = obter_configuracao(db)
    if config is None or not config.emitir_automaticamente:
        return None
    return emitir_nfce(db, provedor, venda)


def consultar_nfce(db: Session, provedor: ProvedorFiscal | None, venda: Venda, atualizar: bool) -> NotaFiscal:
    nota = nota_da_venda(db, venda.id)
    if nota is None:
        raise NaoEncontrado("Esta venda não tem NFC-e")
    if atualizar and provedor is not None and nota.status == "processando":
        try:
            resultado = provedor.consultar(nota.ambiente, str(venda.id))
        except ErroDeConfiguracao as erro:
            raise ErroDeNegocio(str(erro))
        if resultado.status == "nao_encontrada":
            resultado = ResultadoNota(status="erro", mensagem="A NFC-e não chegou ao provedor; reenvie")
        _aplicar(nota, resultado)
        db.commit()
    return nota


def cancelar_nfce(db: Session, provedor: ProvedorFiscal | None, venda: Venda, motivo: str) -> None:
    """Cancela a NFC-e autorizada antes de cancelar a venda. Se a SEFAZ recusar, a venda não é cancelada."""
    nota = db.scalar(select(NotaFiscal).where(NotaFiscal.venda_id == venda.id).with_for_update())
    if nota is None or nota.status in ("rejeitada", "erro", "cancelada"):
        return
    if nota.status == "processando":
        raise Conflito("A NFC-e desta venda ainda está em processamento; consulte antes de cancelar")
    if provedor is None:
        raise ErroDeNegocio("Emissão de NFC-e desligada neste servidor; não é possível cancelar a nota")
    if len(motivo) < JUSTIFICATIVA_MINIMA:
        raise ErroDeNegocio(f"Para cancelar a NFC-e o motivo precisa ter ao menos {JUSTIFICATIVA_MINIMA} caracteres")
    try:
        resultado = provedor.cancelar(nota.ambiente, str(venda.id), motivo)
    except ErroDeConfiguracao as erro:
        raise ErroDeNegocio(str(erro))
    if resultado.status != "cancelada":
        raise ErroDeNegocio(f"A SEFAZ não cancelou a NFC-e: {resultado.mensagem}")
    _aplicar(nota, resultado)
    db.commit()
