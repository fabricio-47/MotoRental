# database.py
import os
import click
from flask import current_app, g

# Postgres
import psycopg2
import psycopg2.extras

# SQLite (fallback p/ rodar local)
import sqlite3

def get_db():
    if "db" not in g:
        database_url = current_app.config.get("DATABASE_URL")

        if database_url:
            # Render às vezes fornece postgres://, mas psycopg2 quer postgresql://
            if database_url.startswith("postgres://"):
                database_url = database_url.replace("postgres://", "postgresql://", 1)

            g.db = psycopg2.connect(
                database_url,
                cursor_factory=psycopg2.extras.RealDictCursor  # -> rows como dict
            )
        else:
            # fallback para SQLite local
            g.db = sqlite3.connect(
                current_app.config.get("DATABASE", "banco.sqlite"),
                detect_types=sqlite3.PARSE_DECLTYPES
            )
            g.db.row_factory = sqlite3.Row  # retorna dict

    return g.db


def close_db(e=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = get_db()
    cur = db.cursor()
    with current_app.open_resource("schema.sql") as f:
        cur.execute(f.read().decode("utf8"))
    db.commit()
    cur.close()


def init_app(app):
    app.teardown_appcontext(close_db)

    @app.cli.command("init-db")
    def init_db_command():
        """Inicializa as tabelas no banco (Postgres ou SQLite)."""
        init_db()
        click.echo("Banco de dados inicializado com sucesso!")