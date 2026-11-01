import secrets
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.central.config import get_config
from app.central.models import HistoricoLicenca, LicencaCentral
from app.central.schemas import LicencaAtualizar, LicencaCriar
from app.licenca.formato import DIAS_DO_PLANO, Licenca, assinar, chave_privada
from app.licenca.situacao import Situacao, situacao
from app.shared.erros import Conflito, ErroDeNegocio, NaoEncontrado, SemPermissao

# Sem 0/O, 1/I: a chave é lida por telefone e digitada à mão.
LETRAS = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"


def hoje() -> date:
    return datetime.now(UTC).date()


def nova_chave_ativacao() -> str:
    return "-".join("".join(secrets.choice(LETRAS) for _ in range(5)) for _ in range(5))


def normalizar_chave(texto: str) -> str:
    letras = "".join(c for c in texto.upper() if c.isalnum())
    return "-".join(letras[i : i + 5] for i in range(0, len(letras), 5))


def normalizar_maquina(texto: str | None) -> str | None:
    if not texto:
        return None
    letras = "".join(c for c in texto.upper() if c.isalnum())
    if len(letras) != 16:
        raise ErroDeNegocio("O código do servidor tem 16 letras e números (ex.: 4F2A-9C1B-77D0-E35A)")
    return "-".join(letras[i : i + 4] for i in range(0, 16, 4))


def vencimento(plano: str, a_partir: date) -> date | None:
    """Mensal: 31 dias contando o dia do cadastro; anual: 365; vitalícia: não vence."""
    dias = DIAS_DO_PLANO[plano]
    return None if dias is None else a_partir + timedelta(days=dias - 1)


def para_licenca(lic: LicencaCentral) -> Licenca:
    return Licenca(
        id=str(lic.id),
        cnpj=lic.cnpj,
        nome=lic.nome,
        tipo=lic.tipo,
        plano=lic.plano,
        inicio=lic.inicio,
        vence=lic.vence,
        tolerancia_dias=lic.tolerancia_dias,
        max_usuarios=lic.max_usuarios,
        max_caixas=lic.max_caixas,
        modulos=lic.modulos,
        maquina=lic.maquina,
        emitida_em=datetime.now(UTC),
    )


def situacao_na_central(lic: LicencaCentral) -> Situacao:
    if lic.suspensa:
        return Situacao(estado="encerrada", bloqueia=True, mensagem="Suspensa: não renova até ser reativada")
    return situacao(para_licenca(lic), hoje(), lic.maquina)


def _anotar(db: Session, lic: LicencaCentral, quem: str, o_que: str) -> None:
    db.add(HistoricoLicenca(licenca_id=lic.id, quem=quem, o_que=o_que))


def listar(db: Session, busca: str | None) -> list[LicencaCentral]:
    consulta = select(LicencaCentral).order_by(LicencaCentral.nome)
    if busca:
        termo = f"%{busca.strip()}%"
        numeros = "".join(c for c in busca if c.isdigit())
        filtros = [LicencaCentral.nome.ilike(termo)]
        if numeros:
            filtros.append(LicencaCentral.cnpj.contains(numeros))
        consulta = consulta.where(or_(*filtros))
    return list(db.scalars(consulta))


def obter(db: Session, licenca_id: int) -> LicencaCentral:
    lic = db.get(LicencaCentral, licenca_id)
    if lic is None:
        raise NaoEncontrado("Licença não encontrada")
    return lic


def criar(db: Session, dados: LicencaCriar, quem: str) -> LicencaCentral:
    inicio = dados.inicio or hoje()
    lic = LicencaCentral(
        **dados.model_dump(exclude={"inicio"}),
        inicio=inicio,
        vence=vencimento(dados.plano, inicio),
        chave_ativacao=nova_chave_ativacao(),
    )
    db.add(lic)
    db.flush()
    _anotar(db, lic, quem, f"Cadastrou ({dados.plano}, {'na farmácia' if dados.tipo == 'farmacia' else 'online'})")
    db.commit()
    return lic


def atualizar(db: Session, licenca_id: int, dados: LicencaAtualizar, quem: str) -> LicencaCentral:
    lic = obter(db, licenca_id)
    # Em branco: limites e módulos ficam sem restrição; os campos obrigatórios só mudam se vierem preenchidos.
    alteracoes = {
        c: v for c, v in dados.model_dump(exclude_unset=True).items()
        if v is not None or c in ("contato", "max_usuarios", "max_caixas", "modulos", "observacao")
    }
    for campo, valor in alteracoes.items():
        setattr(lic, campo, valor)
    if alteracoes.get("plano") == "vitalicio":
        lic.vence = None
    elif "plano" in alteracoes and lic.vence is None:
        lic.vence = vencimento(lic.plano, hoje())
    if alteracoes:
        _anotar(db, lic, quem, "Alterou: " + ", ".join(sorted(alteracoes)))
    db.commit()
    return lic


def renovar(db: Session, licenca_id: int, quem: str) -> LicencaCentral:
    """Mais um período (31 ou 365 dias) a partir do vencimento atual."""
    lic = obter(db, licenca_id)
    if lic.vence is None:
        raise ErroDeNegocio("A licença é vitalícia: não precisa renovar")
    lic.vence = vencimento(lic.plano, lic.vence + timedelta(days=1))
    _anotar(db, lic, quem, f"Renovou até {lic.vence:%d/%m/%Y}")
    db.commit()
    return lic


def liberar_troca(db: Session, licenca_id: int, quem: str) -> LicencaCentral:
    lic = obter(db, licenca_id)
    if lic.maquina:
        _anotar(db, lic, quem, f"Liberou a troca de servidor (era {lic.maquina})")
    lic.maquina = None
    db.commit()
    return lic


def suspender(db: Session, licenca_id: int, suspensa: bool, quem: str) -> LicencaCentral:
    lic = obter(db, licenca_id)
    lic.suspensa = suspensa
    _anotar(db, lic, quem, "Suspendeu" if suspensa else "Reativou")
    db.commit()
    return lic


def _gerar(db: Session, lic: LicencaCentral, maquina: str | None, quem: str) -> str:
    if lic.suspensa:
        raise SemPermissao("Esta licença está suspensa")
    if lic.tipo == "farmacia":
        if maquina is None and lic.maquina is None:
            raise ErroDeNegocio("Informe o código do servidor da farmácia")
        if maquina and lic.maquina and maquina != lic.maquina:
            raise Conflito(
                "Esta licença já está ativada em outro servidor. Libere a troca de computador antes de ativar neste"
            )
        if maquina and lic.maquina is None:
            lic.maquina = maquina
            _anotar(db, lic, quem, f"Ativou no servidor {maquina}")
    lic.ultima_consulta_em = datetime.now(UTC)
    db.commit()
    return assinar(para_licenca(lic), chave_privada(get_config().chave_privada))


def gerar_codigo(db: Session, licenca_id: int, maquina: str | None, quem: str) -> tuple[LicencaCentral, str]:
    lic = obter(db, licenca_id)
    return lic, _gerar(db, lic, normalizar_maquina(maquina), quem)


def ativar(db: Session, chave_ativacao: str, maquina: str | None) -> tuple[LicencaCentral, str]:
    """Chamado pelo próprio servidor (com internet) para ativar ou renovar sozinho."""
    lic = db.scalar(select(LicencaCentral).where(LicencaCentral.chave_ativacao == normalizar_chave(chave_ativacao)))
    if lic is None:
        raise NaoEncontrado("Chave de ativação não encontrada. Confira as letras")
    return lic, _gerar(db, lic, normalizar_maquina(maquina), "o próprio servidor")


def historico(db: Session, licenca_id: int) -> list[HistoricoLicenca]:
    obter(db, licenca_id)
    return list(
        db.scalars(
            select(HistoricoLicenca)
            .where(HistoricoLicenca.licenca_id == licenca_id)
            .order_by(HistoricoLicenca.quando.desc(), HistoricoLicenca.id.desc())
        )
    )
