from alembic import context
from sqlalchemy import create_engine

from app.config import settings

engine = create_engine(
    settings.database_url.replace("postgresql://", "postgresql+psycopg://")
)
with engine.connect() as connection:
    context.configure(connection=connection)
    with context.begin_transaction():
        context.run_migrations()
