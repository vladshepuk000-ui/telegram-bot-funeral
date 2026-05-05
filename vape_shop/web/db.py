import os
import asyncpg

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:jHInKjjHzgONUJeWLNNkoxIumLhqIjIs@tramway.proxy.rlwy.net:56512/railway")


async def get_db() -> asyncpg.Connection:
    """Повертає підключення до PostgreSQL. Закривати вручну після використання."""
    return await asyncpg.connect(DATABASE_URL)
