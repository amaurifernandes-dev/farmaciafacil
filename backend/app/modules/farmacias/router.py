from fastapi import APIRouter
from sqlalchemy.exc import IntegrityError

from app.core.deps import DB, Admin, UsuarioAtual
from app.modules.farmacias.models import Farmacia
from app.modules.farmacias.schemas import (
    PODEM_FICAR_VAZIOS,
    Configuracoes,
    ConfiguracoesAtualizar,
)
from app.modules.licenca.service import modulos_fora
from app.modules.lojas.service import obter_loja
from app.modules.pedidos.pix import normalizar_chave
from app.shared.erros import Conflito, ErroDeNegocio
from app.shared.modulos import MODULOS

router = APIRouter(prefix="/configuracoes", tags=["configurações"])


def _saida(db, farmacia: Farmacia) -> Configuracoes:
    return Configuracoes.model_validate(farmacia).model_copy(
        update={"modulos_fora_da_licenca": modulos_fora(db, farmacia.cnpj)}
    )


@router.get("")
def obter(db: DB, usuario: UsuarioAtual) -> Configuracoes:
    return _saida(db, db.get(Farmacia, usuario.farmacia_id))


@router.patch("")
def atualizar(db: DB, usuario: Admin, dados: ConfiguracoesAtualizar) -> Configuracoes:
    farmacia = db.get(Farmacia, usuario.farmacia_id)
    for campo, valor in dados.model_dump(exclude_unset=True).items():
        if valor is not None or campo in PODEM_FICAR_VAZIOS:
            setattr(farmacia, campo, valor)
    if farmacia.loja_online_loja_id is not None:
        obter_loja(db, farmacia.loja_online_loja_id)
    if dados.entrega_bairros is not None:
        nomes = [b.bairro.strip().casefold() for b in dados.entrega_bairros]
        if len(set(nomes)) != len(nomes):
            raise ErroDeNegocio("Há bairro repetido na lista de taxas de entrega")
        farmacia.entrega_bairros = [
            {"bairro": b.bairro.strip(), "taxa": str(b.taxa)} for b in dados.entrega_bairros
        ]
    if dados.assistente_perfis is not None:
        farmacia.assistente_perfis = sorted(set(dados.assistente_perfis))
    if dados.modulos_desligados is not None:
        farmacia.modulos_desligados = [m for m in MODULOS if m in dados.modulos_desligados]
    if farmacia.pix_chave:
        farmacia.pix_chave = normalizar_chave(farmacia.pix_chave)
    if farmacia.pix_no_site and not (farmacia.pix_chave and farmacia.pix_nome and farmacia.pix_cidade):
        raise ErroDeNegocio("Para receber Pix no site, preencha a chave Pix, o nome e a cidade de quem recebe")
    if farmacia.loja_online_ativa and not farmacia.loja_online_endereco:
        raise ErroDeNegocio("Escolha o endereço da loja online antes de ligar")
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise Conflito("Este endereço de loja online já está em uso. Escolha outro")
    db.refresh(farmacia)
    return _saida(db, farmacia)
