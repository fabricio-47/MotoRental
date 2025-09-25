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

# User loader para Flask-Login
class User(UserMixin):
    def __init__(self, user_id):
        self.id = user_id

@login_manager.user_loader
def load_user(user_id):
    # Aqui você pode validar se o user_id existe no banco
    # Por simplicidade, retornamos sempre um User válido
    return User(user_id)

# Registro dos blueprints
app.register_blueprint(dashboard_bp)  # Dashboard na raiz "/"
app.register_blueprint(auth_bp)
app.register_blueprint(clientes_bp)
app.register_blueprint(motos_bp)
app.register_blueprint(locacoes_bp)
app.register_blueprint(servicos_bp)
app.register_blueprint(webhook_bp)

# Criar pastas de upload se não existirem
@app.before_first_request
def create_upload_folders():
    upload_folder = app.config.get("UPLOAD_FOLDER", "uploads")
    folders = ["contratos", "habilitacoes", "motos"]
    for folder in folders:
        path = os.path.join(upload_folder, folder)
        os.makedirs(path, exist_ok=True)

if __name__ == "__main__":
    app.run(debug=True)