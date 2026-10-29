from fastapi import FastAPI

from app.modules.auth.router import router as auth_router
from app.modules.produtos.router import router as produtos_router
from app.shared.erros import registrar_tratadores

app = FastAPI(title="FarmáciaFácil", version="0.1.0")
registrar_tratadores(app)

app.include_router(auth_router, prefix="/api/v1")
app.include_router(produtos_router, prefix="/api/v1")


@app.get("/api/saude", tags=["infra"])
def saude() -> dict:
    return {"ok": True}
