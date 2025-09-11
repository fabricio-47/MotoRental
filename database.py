# database.py
import psycopg2
import psycopg2.extras
from flask import current_app, g
import click

def get_db():
    if "db" not in g:
        g.db = psycopg2.connect(
            current_app.config["DATABASE_URL"],  
            cursor_factory=psycopg2.extras.RealDictCursor  # rows como dict
        )
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
        """Cria tabelas no Postgres"""
        init_db()
        click.echo("Banco de dados inicializado no Postgres!")