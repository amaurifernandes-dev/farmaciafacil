"""Importa todos os modelos para que o SQLAlchemy e o Alembic conheçam as tabelas."""

from app.modules.auth.models import Usuario  # noqa: F401
from app.modules.farmacias.models import Farmacia  # noqa: F401
from app.modules.lojas.models import Loja, Terminal  # noqa: F401
from app.modules.clientes.models import Cliente  # noqa: F401
from app.modules.fornecedores.models import Fornecedor  # noqa: F401
from app.modules.produtos.models import Produto, ProdutoCodigo  # noqa: F401
from app.modules.estoque.models import Lote, MovimentoEstoque  # noqa: F401
from app.modules.vendas.models import Caixa, PreVenda, Venda, VendaItem, VendaPagamento  # noqa: F401
from app.modules.fiscal.models import ConfiguracaoFiscal, NotaFiscal  # noqa: F401
from app.modules.compras.models import NotaEntrada, NotaEntradaItem, ProdutoFornecedor  # noqa: F401
from app.modules.financeiro.models import Conta  # noqa: F401
from app.modules.fidelidade.models import MovimentoPontos  # noqa: F401
from app.modules.promocoes.models import Promocao, PromocaoProduto  # noqa: F401
from app.modules.faltas.models import Falta  # noqa: F401
from app.modules.pedidos.models import Pedido, PedidoItem  # noqa: F401
from app.modules.controlados.models import Receita  # noqa: F401
from app.modules.convenios.models import CompraConvenio, Convenio  # noqa: F401
from app.modules.popular.models import VendaPopular  # noqa: F401
from app.modules.etiquetas.models import Etiqueta  # noqa: F401
from app.modules.metas.models import Meta  # noqa: F401
from app.modules.inventario.models import Inventario, ItemInventario  # noqa: F401
from app.modules.servicos.models import AtendimentoServico, Servico  # noqa: F401
from app.modules.devolucoes.models import Devolucao, ItemDevolucao, ValeTroca  # noqa: F401
