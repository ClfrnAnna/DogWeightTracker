from sqlalchemy import text
from database import engine


async def create_application_tables():
    sql_statements = \
        [
            """CREATE EXTENSION IF NOT EXISTS "uuid-ossp";""",
            """CREATE TABLE IF NOT EXISTS application_logs (
            id SERIAL PRIMARY KEY,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            level VARCHAR(10),
            message TEXT,
            service VARCHAR(50)
        );"""
        ]

    async with engine.begin() as conn:
        for sql in sql_statements:
            try:
                await conn.execute(text(sql))
                print(f"Выполнен SQL: {sql[:50]}...")
            except Exception as e:
                print(f"Ошибка при выполнении SQL: {e}")
