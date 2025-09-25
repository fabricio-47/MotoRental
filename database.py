import psycopg2
from psycopg2.extras import RealDictCursor
import os
from config import Config

def get_db_connection():
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        # Render fornece a string completa, ex:
        # postgresql://user:pass@host:5432/dbname
        return psycopg2.connect(database_url, sslmode="require", cursor_factory=RealDictCursor)
    else:
        # Fallback para ambiente local
        return psycopg2.connect(
            host=Config.DB_HOST,
            database=Config.DB_NAME,
            user=Config.DB_USER,
            password=Config.DB_PASSWORD,
            sslmode=Config.DB_SSLMODE,
            cursor_factory=RealDictCursor
        )