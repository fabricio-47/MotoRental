import os
from flask import Flask, render_template, request, redirect, url_for, flash, session, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from database import get_db, init_app

app = Flask(__name__)

# Configurações
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-key")
app.config["DATABASE_URL"] = os.environ.get("DATABASE_URL")  # Postgres no Render

# 🔹 Configuração para uploads de imagens de motos
UPLOAD_FOLDER_MOTOS = os.path.join(os.getcwd(), "uploads_motos")
os.makedirs(UPLOAD_FOLDER_MOTOS, exist_ok=True)
app.config["UPLOAD_FOLDER_MOTOS"] = UPLOAD_FOLDER_MOTOS
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# 🔹 Configuração para upload de contratos (PDF)
UPLOAD_FOLDER_CONTRATOS = os.path.join(os.getcwd(), "uploads_contratos")
os.makedirs(UPLOAD_FOLDER_CONTRATOS, exist_ok=True)
app.config["UPLOAD_FOLDER_CONTRATOS"] = UPLOAD_FOLDER_CONTRATOS
ALLOWED_CONTRACT_EXTENSIONS = {'pdf'}

def allowed_contract(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_CONTRACT_EXTENSIONS

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

        cur.execute("SELECT id, username, email, senha FROM usuarios WHERE email = %s", (email,))
        user = cur.fetchone()

        if user and check_password_hash(user["senha"], senha):
            session["user_id"] = user["id"]
            session["user_email"] = user["email"]
            session["username"] = user["username"]
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


# IMAGENS DAS MOTOS
@app.route("/motos/<int:moto_id>/imagens", methods=["GET", "POST"])
def moto_imagens(moto_id):
    conn = get_db()
    cur = conn.cursor()

    if request.method == "POST":
        if "imagem" in request.files:
            file = request.files["imagem"]
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                path = os.path.join(app.config["UPLOAD_FOLDER_MOTOS"], filename)
                file.save(path)

                cur.execute(
                    "INSERT INTO moto_imagens (moto_id, arquivo) VALUES (%s, %s)",
                    (moto_id, filename)
                )
                conn.commit()

    cur.execute("SELECT * FROM moto_imagens WHERE moto_id = %s ORDER BY data_upload DESC", (moto_id,))
    imagens = cur.fetchall()

    cur.execute("SELECT id, modelo, placa, ano FROM motos WHERE id=%s", (moto_id,))
    moto = cur.fetchone()

    cur.close()
    return render_template("moto_imagens.html", moto=moto, imagens=imagens)


@app.route("/motos/<int:moto_id>/imagens/<int:imagem_id>/excluir", methods=["POST"])
def excluir_imagem_moto(moto_id, imagem_id):
    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT arquivo FROM moto_imagens WHERE id = %s AND moto_id = %s", (imagem_id, moto_id))
    imagem = cur.fetchone()

    if imagem:
        arquivo_path = os.path.join(app.config["UPLOAD_FOLDER_MOTOS"], imagem["arquivo"])
        if os.path.exists(arquivo_path):
            os.remove(arquivo_path)

        cur.execute("DELETE FROM moto_imagens WHERE id = %s AND moto_id = %s", (imagem_id, moto_id))
        conn.commit()

    cur.close()
    return redirect(url_for('moto_imagens', moto_id=moto_id))


# LOCAÇÕES (ATUALIZADA COM OBSERVAÇÕES + CONTRATO PDF)
@app.route("/locacoes", methods=["GET", "POST"])
def locacoes():
    conn = get_db()
    cur = conn.cursor()

    if request.method == "POST":
        cliente_id = request.form["cliente_id"]
        moto_id = request.form["moto_id"]
        data_inicio = request.form["data_inicio"]
        observacoes = request.form.get("observacoes")

        # 🔹 Upload do contrato PDF
        contrato_pdf = None
        if "contrato_pdf" in request.files:
            file = request.files["contrato_pdf"]
            if file and allowed_contract(file.filename):
                filename = secure_filename(file.filename)
                contrato_path = os.path.join(app.config["UPLOAD_FOLDER_CONTRATOS"], filename)
                file.save(contrato_path)
                contrato_pdf = filename

        # cria locação
        cur.execute("""
            INSERT INTO locacoes (cliente_id, moto_id, data_inicio, observacoes, contrato_pdf) 
            VALUES (%s,%s,%s,%s,%s)
        """, (cliente_id, moto_id, data_inicio, observacoes, contrato_pdf))

        # marca moto como não disponível
        cur.execute("UPDATE motos SET disponivel=FALSE WHERE id=%s", (moto_id,))
        conn.commit()
        return redirect(url_for("locacoes"))

    # 🔹 locações ativas (inclui observações e contrato)
    cur.execute("""SELECT l.id, 
                          c.nome, 
                          m.modelo, 
                          m.placa,
                          l.data_inicio, 
                          l.data_fim, 
                          l.cancelado,
                          l.observacoes,
                          l.contrato_pdf
                   FROM locacoes l
                   JOIN clientes c ON l.cliente_id=c.id
                   JOIN motos m ON l.moto_id=m.id
                   WHERE l.cancelado = FALSE""")
    locacoes = cur.fetchall()

    # 🔹 clientes
    cur.execute("SELECT id, nome FROM clientes")
    clientes = cur.fetchall()

    # 🔹 motos disponíveis
    cur.execute("SELECT id, modelo, placa FROM motos WHERE disponivel=TRUE")
    motos = cur.fetchall()

    cur.close()
    return render_template("locacoes.html", locacoes=locacoes, clientes=clientes, motos=motos)


@app.route("/locacoes/<int:id>/cancelar", methods=["POST"])
def cancelar_locacao(id):
    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT moto_id FROM locacoes WHERE id = %s", (id,))
    locacao = cur.fetchone()
    if locacao:
        moto_id = locacao["moto_id"]
        cur.execute("UPDATE locacoes SET cancelado = TRUE WHERE id = %s", (id,))
        cur.execute("UPDATE motos SET disponivel = TRUE WHERE id = %s", (moto_id,))
        conn.commit()

    cur.close()
    return redirect(url_for("locacoes"))


# Servir imagens (rota pública)
@app.route('/uploads_motos/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER_MOTOS'], filename)


# 🔹 Servir contratos PDF (rota pública)
@app.route('/uploads_contratos/<path:filename>')
def uploaded_contract(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER_CONTRATOS'], filename)


# Rodar localmente
if __name__ == "__main__":
    app.run(debug=True)