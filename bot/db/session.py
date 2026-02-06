from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from bot.config import Settings


def create_engine(settings: Settings):
    return create_async_engine(settings.database_url, echo=False)


def create_sessionmaker(settings: Settings):
    engine = create_engine(settings)
    session_maker = async_sessionmaker(engine, expire_on_commit=False)
    return engine, session_maker
