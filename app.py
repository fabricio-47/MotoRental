import os
from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
from database import get_db, init_app

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-key")

# URL do Postgres via variável de ambiente
app.config["DATABASE_URL"] = os.environ.get("DATABASE_URL")

# inicializa funções de db
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
    conn = get_db()
    cur = conn.cursor()
    if request.method == "POST":
        email = request.form["email"]
        senha = request.form["senha"]
        cur.execute("SELECT id, email, senha FROM usuarios WHERE email = %s", (email,))
        user = cur.fetchone()
        if user and check_password_hash(user[2], senha):
            session["user_id"] = user[0]
            return redirect(url_for("dashboard"))
        else:
            flash("E-mail ou senha inválidos", "error")
    cur.close()
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# DASHBOARD
@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("login"))
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM motos")
    total_motos = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM clientes")
    total_clientes = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM locacoes WHERE data_fim IS NULL")
    locacoes_ativas = cur.fetchone()[0]

    cur.close()
    stats = {"total_motos": total_motos, "total_clientes": total_clientes, "locacoes_ativas": locacoes_ativas}
    return render_template("dashboard.html", stats=stats)


# MOTOS
@app.route("/motos", methods=["GET", "POST"])
def motos():
    conn = get_db()
    cur = conn.cursor()
    if request.method == "POST":
        placa = request.form["placa"]
        modelo = request.form["modelo"]
        ano = request.form["ano"]
        cur.execute("INSERT INTO motos (placa, modelo, ano) VALUES (%s,%s,%s)",
                    (placa, modelo, ano))
        conn.commit()
        return redirect(url_for("motos"))

    cur.execute("SELECT id, placa, modelo, ano, disponivel FROM motos")
    motos = cur.fetchall()
    cur.close()
    return render_template("motos.html", motos=motos)


# CLIENTES
@app.route("/clientes", methods=["GET", "POST"])
def clientes():
    conn = get_db()
    cur = conn.cursor()
    if request.method == "POST":
        nome = request.form["nome"]
        email = request.form["email"]
        telefone = request.form["telefone"]
        cur.execute("INSERT INTO clientes (nome, email, telefone) VALUES (%s,%s,%s)",
                    (nome, email, telefone))
        conn.commit()
        return redirect(url_for("clientes"))

    cur.execute("SELECT id, nome, email, telefone FROM clientes")
    clientes = cur.fetchall()
    cur.close()
    return render_template("clientes.html", clientes=clientes)


# LOCAÇÕES
@app.route("/locacoes", methods=["GET", "POST"])
def locacoes():
    conn = get_db()
    cur = conn.cursor()
    if request.method == "POST":
        cliente_id = request.form["cliente_id"]
        moto_id = request.form["moto_id"]
        data_inicio = request.form["data_inicio"]
        cur.execute("INSERT INTO locacoes (cliente_id, moto_id, data_inicio) VALUES (%s,%s,%s)",
                    (cliente_id, moto_id, data_inicio))
        cur.execute("UPDATE motos SET disponivel=FALSE WHERE id=%s", (moto_id,))
        conn.commit()
        return redirect(url_for("locacoes"))

    cur.execute("""SELECT l.id, c.nome, m.modelo, l.data_inicio, l.data_fim
                   FROM locacoes l
                   JOIN clientes c ON l.cliente_id=c.id
                   JOIN motos m ON l.moto_id=m.id""")
    locacoes = cur.fetchall()

    cur.execute("SELECT id, nome FROM clientes")
    clientes = cur.fetchall()

    cur.execute("SELECT id, modelo FROM motos WHERE disponivel=TRUE")
    motos = cur.fetchall()

    cur.close()
    return render_template("locacoes.html", locacoes=locacoes, clientes=clientes, motos=motos)


if __name__ == "__main__":
    app.run(debug=True)