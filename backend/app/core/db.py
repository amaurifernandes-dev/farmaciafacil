from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

engine = create_engine(get_settings().database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(engine, expire_on_commit=False)


@event.listens_for(SessionLocal, "after_begin")
def _definir_farmacia(session: Session, transaction, connection) -> None:
    """Em toda transação, informa ao Postgres qual farmácia está ativa.

    As políticas de RLS leem esse valor. O terceiro argumento `true` deixa o
    valor restrito à transação, o que é seguro com pool de conexões (Neon).
    """
    farmacia_id = session.info.get("farmacia_id")
    if farmacia_id is not None:
        connection.execute(
            text("SELECT set_config('app.farmacia_id', :id, true)"),
            {"id": str(farmacia_id)},
        )
