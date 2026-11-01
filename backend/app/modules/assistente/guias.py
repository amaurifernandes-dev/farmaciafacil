"""Guias passo a passo das telas, que o assistente explica e abre ("Começar")."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Guia:
    id: str
    titulo: str
    rota: str
    passos: tuple[str, ...]


GUIAS: tuple[Guia, ...] = (
    Guia(
        "receber_nota", "Dar entrada nos produtos que chegaram do fornecedor (nota fiscal)", "/compras",
        (
            "Em Compras, na área \"Importar XML da nota\", clique em \"Escolher arquivo XML\" e escolha o XML que o fornecedor mandou.",
            "O sistema lê a nota e lista os itens. Abra a nota na lista \"Últimas notas\".",
            "Para cada item sem produto ligado, clique em \"Escolher produto\" e ligue ao produto do sistema (ou cadastre um novo ali mesmo).",
            "Confira as quantidades que entram no estoque e as validades dos lotes.",
            "Clique em \"Confirmar entrada no estoque\". Pronto: o estoque e o custo são atualizados.",
        ),
    ),
    Guia(
        "entrada_manual", "Dar entrada no estoque sem nota (entrada manual)", "/estoque/entrada",
        (
            "Em Estoque, abra \"Entrada manual\".",
            "Busque cada produto e informe a quantidade, o lote e a validade.",
            "Escreva uma observação (por exemplo, o número da nota ou o fornecedor).",
            "Salve a entrada. O saldo do produto aumenta na hora.",
        ),
    ),
    Guia(
        "cadastrar_produto", "Cadastrar um produto novo", "/configuracoes/produtos",
        (
            "Em Configurações, abra \"Produtos\" e clique em \"Novo produto\".",
            "Preencha o nome, a apresentação, o código de barras (EAN) e o preço de venda.",
            "Se souber, informe o preço de custo, o estoque mínimo e os dados fiscais (NCM).",
            "Clique em \"Salvar\". Para o produto ter estoque, dê entrada pela nota ou pela entrada manual.",
        ),
    ),
    Guia(
        "cadastrar_cliente", "Cadastrar um cliente", "/clientes",
        (
            "Em Clientes, clique em \"Novo cliente\".",
            "Preencha o nome completo e, se tiver, CPF, telefone, data de nascimento e endereço.",
            "Marque \"Autoriza receber ofertas e descontos\" só se o cliente aceitar.",
            "Salve. Também posso cadastrar por você: é só me falar os dados.",
        ),
    ),
    Guia(
        "pre_venda", "Fazer uma pré-venda no balcão", "/vendas/pre-venda",
        (
            "Abra \"Nova pré-venda\".",
            "Bipe o código de barras ou digite o nome do produto e clique em \"Buscar\". Adicione os produtos ao pedido.",
            "Se quiser, informe o CPF do cliente.",
            "Envie a pré-venda. O número aparece na tela: o cliente paga no caixa com esse número (F7 no PDV).",
            "Também posso montar a pré-venda por você: é só me dizer os produtos.",
        ),
    ),
    Guia(
        "vender_pdv", "Vender no caixa (PDV)", "/pdv",
        (
            "Abra o PDV. Se o caixa estiver fechado, informe o dinheiro da gaveta e abra.",
            "Bipe os produtos (ou F2 para buscar pelo nome). F3 muda a quantidade e F6 dá desconto.",
            "Aperte F4 para o pagamento e escolha a forma (Alt+1 dinheiro, Alt+2 débito, Alt+3 crédito, Alt+4 Pix).",
            "Digite o valor recebido e aperte Enter. Com o valor completo, Enter finaliza a venda.",
            "F7 recebe uma pré-venda, F8 identifica o cliente e F9 usa os pontos dele.",
        ),
    ),
    Guia(
        "fechar_caixa", "Fechar o caixa", "/pdv",
        (
            "No PDV, com a venda vazia, aperte F10.",
            "Confira o resumo: vendas por forma de pagamento e o dinheiro esperado na gaveta.",
            "Conte o dinheiro e digite o valor contado. Aperte Enter.",
            "O sistema mostra a diferença (sobra ou falta). O gerente acompanha em Caixas.",
        ),
    ),
    Guia(
        "troca_devolucao", "Fazer uma troca ou devolução", "/devolucoes",
        (
            "Em Trocas e devoluções, digite o número da venda.",
            "Informe a quantidade devolvida de cada item e o motivo.",
            "Escolha devolver em dinheiro ou gerar um vale-troca.",
            "Clique em \"Confirmar devolução\" e imprima o comprovante.",
        ),
    ),
    Guia(
        "promocao", "Criar uma promoção", "/promocoes",
        (
            "Em Promoções, clique em \"Nova promoção\".",
            "Escolha o tipo: desconto em %, preço especial ou leve e pague.",
            "Digite o nome dos produtos para incluir e defina o início e o fim.",
            "Clique em \"Salvar\". O PDV já aplica a promoção. Depois imprima as etiquetas novas em Etiquetas de preço.",
        ),
    ),
    Guia(
        "etiquetas", "Imprimir etiquetas de preço", "/etiquetas",
        (
            "Em Etiquetas de preço, veja os produtos que precisam de etiqueta nova (preço mudou ou entrou em promoção).",
            "Marque os produtos (ou \"Marcar todos\").",
            "Escolha o modelo: gôndola, gôndola pequena ou cartaz de oferta.",
            "Clique para imprimir.",
        ),
    ),
    Guia(
        "inventario", "Fazer o inventário (contagem do estoque)", "/estoque/inventario",
        (
            "Em Estoque, abra Inventário e, em \"Abrir uma contagem\", escolha um inventário geral ou de alguns produtos.",
            "Conte os produtos na prateleira e registre as quantidades na contagem.",
            "Confira as diferenças entre o contado e o sistema.",
            "Finalize: o sistema acerta o saldo do estoque.",
        ),
    ),
    Guia(
        "transferencia", "Transferir produtos entre lojas", "/estoque/transferencia",
        (
            "Em Estoque, abra \"Transferir entre lojas\".",
            "Escolha a loja de destino em \"Vai para\".",
            "Adicione os produtos e as quantidades.",
            "Confirme. O estoque sai de uma loja e entra na outra.",
        ),
    ),
    Guia(
        "contas", "Lançar e pagar contas", "/financeiro",
        (
            "Abra Financeiro.",
            "Lance a conta com a descrição, o valor e o vencimento.",
            "Quando pagar, marque a conta como paga.",
            "Acompanhe o saldo em Fluxo de caixa.",
        ),
    ),
    Guia(
        "vendas_sem_internet", "Ver as vendas feitas sem internet", "/vendas-offline",
        (
            "Abra \"Vendas sem internet\" no menu (só gerente).",
            "Em \"Recusadas para resolver\", veja o que não entrou e o motivo.",
            "Em \"Vendidos sem estoque\", confira esses produtos na prateleira e acerte no inventário.",
            "Depois de resolver uma recusada à mão, clique em \"Já resolvi\".",
        ),
    ),
)

POR_ID = {g.id: g for g in GUIAS}


def lista_para_ferramenta() -> str:
    return "\n".join(f"- {g.id}: {g.titulo}" for g in GUIAS)
