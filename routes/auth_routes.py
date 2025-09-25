from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_login import login_user, logout_user, login_required

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")

# Login
@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")     # 👈 bate com login.html
        senha = request.form.get("senha")     # 👈 bate com login.html

        # Aqui implemente validação real com banco / hash de senha
        if email == "admin" and senha == "admin":
            session["user_id"] = 1
            flash("Login efetuado!", "success")
            return redirect(url_for("locacoes.listar_locacoes"))

        flash("Usuário ou senha incorretos!", "danger")

    return render_template("login.html")

# Logout
@auth_bp.route("/logout")
@login_required
def logout():
    session.clear()
    logout_user()
    flash("Logout realizado!", "success")
    return redirect(url_for("auth.login"))