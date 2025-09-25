from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_login import login_user, logout_user, login_required

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")

# Login
@auth_bp.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        # Aqui implemente validação com seu banco / usuário admin
        if username == "admin" and password == "admin":
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