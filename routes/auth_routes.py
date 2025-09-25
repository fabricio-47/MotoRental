from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, UserMixin

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")

# Usuário simples para ambiente de teste (admin/admin)
# Em produção, substitua por um modelo buscado do banco que herde de UserMixin.
class SimpleUser(UserMixin):
    def __init__(self, id, email):
        self.id = str(id)  # Flask-Login trabalha com string
        self.email = email

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")   # bate com login.html
        senha = request.form.get("senha")   # bate com login.html
        remember = bool(request.form.get("remember"))

        # Validação temporária (trocar por validação com banco + check_password_hash)
        if email == "admin" and senha == "admin":
            user = SimpleUser(id=1, email=email)
            login_user(user, remember=remember)
            flash("Login efetuado!", "success")

            next_url = request.form.get("next") or request.args.get("next")
            return redirect(next_url or url_for("locacoes.listar_locacoes"))

        flash("Usuário ou senha incorretos!", "danger")

    return render_template("login.html")

@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Logout realizado!", "success")
    return redirect(url_for("auth.login"))