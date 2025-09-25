from flask import Flask
from flask_login import LoginManager, UserMixin
import os

from config import Config
from routes.auth_routes import auth_bp
from routes.clientes_routes import clientes_bp
from routes.motos_routes import motos_bp
from routes.locacoes_routes import locacoes_bp
from routes.servicos_routes import servicos_bp
from routes.webhook_routes import webhook_bp
from routes.dashboard_routes import dashboard_bp

# Inicialização
app = Flask(__name__)
app.config.from_object(Config)

# Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "auth.login"
login_manager.login_message = "Faça login para acessar esta página."
login_manager.login_message_category = "info"

# User loader
class User(UserMixin):
    def __init__(self, user_id):
        self.id = user_id

@login_manager.user_loader
def load_user(user_id):
    return User(user_id)

# Registro dos blueprints
app.register_blueprint(dashboard_bp)  # Dashboard na raiz "/"
app.register_blueprint(auth_bp)
app.register_blueprint(clientes_bp)
app.register_blueprint(motos_bp)
app.register_blueprint(locacoes_bp)
app.register_blueprint(servicos_bp)
app.register_blueprint(webhook_bp)

# Criar pastas de upload logo na inicialização do app (Flask 3.x removeu before_first_request)
upload_folder = app.config.get("UPLOAD_FOLDER", "uploads")
for folder in ["contratos", "habilitacoes", "motos"]:
    path = os.path.join(upload_folder, folder)
    os.makedirs(path, exist_ok=True)

if __name__ == "__main__":
    app.run(debug=True)

import click
from flask.cli import with_appcontext
from database import get_db_connection

@click.command("init-db")
@with_appcontext
def init_db_command():
    """Inicializa o banco de dados aplicando o schema.sql"""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        with open("schema.sql", "r", encoding="utf-8") as f:
            sql_code = f.read()
            cur.execute(sql_code)
        conn.commit()
        click.echo("✅ Banco de dados inicializado com sucesso!")
    except Exception as e:
        conn.rollback()
        click.echo(f"❌ Erro ao inicializar o banco: {e}")
    finally:
        cur.close()
        conn.close()

# Registra o comando personalizado no Flask CLI
app.cli.add_command(init_db_command)