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
