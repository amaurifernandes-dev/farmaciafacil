from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.central.config import get_config


@lru_cache
def engine() -> Engine:
    return create_engine(get_config().database_url, pool_pre_ping=True)


def sessao() -> Session:
    return sessionmaker(engine(), expire_on_commit=False)()


def get_db() -> Iterator[Session]:
    db = sessao()
    try:
        yield db
    finally:
        db.close()
