from fastapi import FastAPI

from app.central.router import router
from app.shared.erros import registrar_tratadores

app = FastAPI(title="FarmáciaFácil - Central de licenças", version="0.1.0")
registrar_tratadores(app)
app.include_router(router)
