from uuid import UUID

from pydantic import BaseModel, EmailStr


class LoginEntrada(BaseModel):
    email: EmailStr
    senha: str


class LoginSaida(BaseModel):
    access_token: str
    token_type: str = "bearer"
    usuario_id: UUID
    farmacia_id: UUID
    nome: str
    papel: str
