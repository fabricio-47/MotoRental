import sqlite3
from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
from database import get_db, init_app

app = Flask(__name__)
app.config["SECRET_KEY"] = "uma-chave-super-secreta"
app.config["DATABASE"] = "banco.sqlite"

# inicializa banco
init_app(app)

# ---------- ROTAS ----------

@app.route("/")
def home():
    if "user_id" not in session:
        return redirect(url_for("login"))
    return redirect(url_for("dashboard"))

# LOGIN
@app.route("/login", methods=["GET", "POST"])
def login():
    db = get_db()
    if request.method == "POST":
        email = request.form["email"]
        senha = request.form["senha"]
        user = db.execute("SELECT * FROM usuarios WHERE email = ?", (email,)).fetchone()
        if user and check_password_hash(user["senha"], senha):
            session["user_id"] = user["id"]
            return redirect(url_for("dashboard"))
        else:
            flash("E-mail ou senha inválidos", "error")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# DASH
@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("login"))
    db = get_db()
    total_motos = db.execute("SELECT COUNT(*) FROM motos").fetchone()[0]
    total_clientes = db.execute("SELECT COUNT(*) FROM clientes").fetchone()[0]
    locacoes_ativas = db.execute("SELECT COUNT(*) FROM locacoes WHERE data_fim IS NULL").fetchone()[0]
    stats = {"total_motos": total_motos, "total_clientes": total_clientes, "locacoes_ativas": locacoes_ativas}
    return render_template("dashboard.html", stats=stats)

# MOTOS
@app.route("/motos", methods=["GET", "POST"])
def motos():
    db = get_db()
    if request.method == "POST":
        placa = request.form["placa"]
        modelo = request.form["modelo"]
        ano = request.form["ano"]
        db.execute("INSERT INTO motos (placa, modelo, ano) VALUES (?,?,?)", (placa, modelo, ano))
        db.commit()
        return redirect(url_for("motos"))
    motos = db.execute("SELECT * FROM motos").fetchall()
    return render_template("motos.html", motos=motos)

# CLIENTES
@app.route("/clientes", methods=["GET", "POST"])
def clientes():
    db = get_db()
    if request.method == "POST":
        nome = request.form["nome"]
        email = request.form["email"]
        telefone = request.form["telefone"]
        db.execute("INSERT INTO clientes (nome,email,telefone) VALUES (?,?,?)", (nome, email, telefone))
        db.commit()
        return redirect(url_for("clientes"))
    clientes = db.execute("SELECT * FROM clientes").fetchall()
    return render_template("clientes.html", clientes=clientes)

# LOCAÇÕES
@app.route("/locacoes", methods=["GET", "POST"])
def locacoes():
    db = get_db()
    if request.method == "POST":
        cliente_id = request.form["cliente_id"]
        moto_id = request.form["moto_id"]
        data_inicio = request.form["data_inicio"]
        db.execute("INSERT INTO locacoes (cliente_id,moto_id,data_inicio) VALUES (?,?,?)",
                   (cliente_id, moto_id, data_inicio))
        db.execute("UPDATE motos SET disponivel=0 WHERE id=?", (moto_id,))
        db.commit()
        return redirect(url_for("locacoes"))

    locacoes = db.execute("""SELECT l.id,c.nome,m.modelo,l.data_inicio,l.data_fim
                              FROM locacoes l
                              JOIN clientes c ON l.cliente_id=c.id
                              JOIN motos m ON l.moto_id=m.id""").fetchall()

    clientes = db.execute("SELECT * FROM clientes").fetchall()
    motos = db.execute("SELECT * FROM motos WHERE disponivel=1").fetchall()
    return render_template("locacoes.html", locacoes=locacoes, clientes=clientes, motos=motos)

if __name__ == "__main__":
    app.run(debug=True)