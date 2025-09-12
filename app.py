import os
from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
from database import get_db, init_app

app = Flask(__name__)

# Configurações
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-key")
app.config["DATABASE_URL"] = os.environ.get("DATABASE_URL")  # Postgres no Render

# Inicializa funções de banco
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

        # 🔄 1. Query agora busca também o username
        cur.execute("SELECT id, username, email, senha FROM usuarios WHERE email = %s", (email,))
        user = cur.fetchone()

        if user and check_password_hash(user["senha"], senha):
            # 🔄 2. Além do user_id e user_email, também salvamos o username
            session["user_id"] = user["id"]
            session["user_email"] = user["email"]
            session["username"] = user["username"]   # <-- ADICIONADO

            return redirect(url_for("dashboard"))
        else:
            flash("E-mail ou senha inválidos", "error")

    cur.close()
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/dashboard")
def dashboard():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) AS total FROM clientes")
    total_clientes = cur.fetchone()["total"]

    cur.execute("SELECT COUNT(*) AS total FROM motos")
    total_motos = cur.fetchone()["total"]

    cur.execute("SELECT COUNT(*) AS total FROM locacoes WHERE cancelado = FALSE")
    locacoes_ativas = cur.fetchone()["total"]

    cur.execute("SELECT COUNT(*) AS total FROM locacoes WHERE cancelado = TRUE")
    locacoes_canceladas = cur.fetchone()["total"]

    cur.close()
    return render_template(
        "dashboard.html",
        total_clientes=total_clientes,
        total_motos=total_motos,
        locacoes_ativas=locacoes_ativas,
        locacoes_canceladas=locacoes_canceladas
    )

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

    cur.execute("SELECT * FROM motos")
    motos = cur.fetchall()
    cur.close()
    return render_template("motos.html", motos=motos)


@app.route("/clientes", methods=["GET", "POST"])
def clientes():
    conn = get_db()
    cur = conn.cursor()
    if request.method == "POST":
        nome = request.form["nome"]
        email = request.form["email"]
        telefone = request.form["telefone"]
        cpf = request.form.get("cpf")
        endereco = request.form.get("endereco")
        data_nascimento = request.form.get("data_nascimento")
        observacoes = request.form.get("observacoes")

        cur.execute("""
            INSERT INTO clientes 
                (nome, email, telefone, cpf, endereco, data_nascimento, observacoes) 
            VALUES (%s,%s,%s,%s,%s,%s,%s)
        """, (nome, email, telefone, cpf, endereco, data_nascimento, observacoes))
        conn.commit()
        return redirect(url_for("clientes"))

    cur.execute("SELECT * FROM clientes")
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

        # cria locação
        cur.execute("INSERT INTO locacoes (cliente_id, moto_id, data_inicio) VALUES (%s,%s,%s)",
                    (cliente_id, moto_id, data_inicio))
        # marca moto como não disponível
        cur.execute("UPDATE motos SET disponivel=FALSE WHERE id=%s", (moto_id,))
        conn.commit()
        return redirect(url_for("locacoes"))

    # traz apenas locações não canceladas
    cur.execute("""SELECT l.id, c.nome, m.modelo, l.data_inicio, l.data_fim, l.cancelado
                   FROM locacoes l
                   JOIN clientes c ON l.cliente_id=c.id
                   JOIN motos m ON l.moto_id=m.id
                   WHERE l.cancelado = FALSE""")
    locacoes = cur.fetchall()

    cur.execute("SELECT id, nome FROM clientes")
    clientes = cur.fetchall()

    cur.execute("SELECT id, modelo FROM motos WHERE disponivel=TRUE")
    motos = cur.fetchall()

    cur.close()
    return render_template("locacoes.html", locacoes=locacoes, clientes=clientes, motos=motos)


# Rota para cancelar locação
@app.route("/locacoes/<int:id>/cancelar", methods=["POST"])
def cancelar_locacao(id):
    conn = get_db()
    cur = conn.cursor()

    # pega moto vinculada
    cur.execute("SELECT moto_id FROM locacoes WHERE id = %s", (id,))
    locacao = cur.fetchone()
    if locacao:
        moto_id = locacao["moto_id"]
        cur.execute("UPDATE locacoes SET cancelado = TRUE WHERE id = %s", (id,))
        cur.execute("UPDATE motos SET disponivel = TRUE WHERE id = %s", (moto_id,))
        conn.commit()

    cur.close()
    return redirect(url_for("locacoes"))

# Rodar localmente
if __name__ == "__main__":
    app.run(debug=True)