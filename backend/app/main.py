from fastapi import FastAPI

from app.modules import todos_os_modelos  # noqa: F401  (registra as tabelas)
from app.modules.auth.router import router as auth_router
from app.modules.auth.usuarios import router as usuarios_router
from app.modules.clientes.router import router as clientes_router
from app.modules.compras.router import router as compras_router
from app.modules.estoque.router import router as estoque_router
from app.modules.farmacias.router import router as configuracoes_router
from app.modules.fornecedores.router import router as fornecedores_router
from app.modules.lojas.router import lojas as lojas_router
from app.modules.lojas.router import terminais as terminais_router
from app.modules.painel.router import router as painel_router
from app.modules.fiscal.router import router as fiscal_router
from app.modules.produtos.router import router as produtos_router
from app.modules.vendas.router import caixas as caixas_router
from app.modules.vendas.router import pre_vendas as pre_vendas_router
from app.modules.vendas.router import vendas as vendas_router
from app.shared.erros import registrar_tratadores

app = FastAPI(title="FarmáciaFácil", version="0.1.0")
registrar_tratadores(app)

app.include_router(auth_router, prefix="/api/v1")
app.include_router(produtos_router, prefix="/api/v1")
app.include_router(estoque_router, prefix="/api/v1")
app.include_router(compras_router, prefix="/api/v1")
app.include_router(caixas_router, prefix="/api/v1")
app.include_router(vendas_router, prefix="/api/v1")
app.include_router(pre_vendas_router, prefix="/api/v1")
app.include_router(painel_router, prefix="/api/v1")
app.include_router(clientes_router, prefix="/api/v1")
app.include_router(fornecedores_router, prefix="/api/v1")
app.include_router(usuarios_router, prefix="/api/v1")
app.include_router(lojas_router, prefix="/api/v1")
app.include_router(terminais_router, prefix="/api/v1")
app.include_router(configuracoes_router, prefix="/api/v1")
app.include_router(fiscal_router, prefix="/api/v1")


@app.get("/api/saude", tags=["infra"])
def saude() -> dict:
    return {"ok": True}
