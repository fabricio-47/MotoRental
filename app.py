import os
from flask import Flask, render_template, request, redirect, url_for, flash, session, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import psycopg2.extras
from database import get_db, init_app

app = Flask(__name__)

# Configurações
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-key")
app.config["DATABASE_URL"] = os.environ.get("DATABASE_URL")  # Postgres no Render

# 🔹 Uploads
UPLOAD_FOLDER_MOTOS = os.path.join(os.getcwd(), "uploads_motos")
os.makedirs(UPLOAD_FOLDER_MOTOS, exist_ok=True)
app.config["UPLOAD_FOLDER_MOTOS"] = UPLOAD_FOLDER_MOTOS
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

UPLOAD_FOLDER_CONTRATOS = os.path.join(os.getcwd(), "uploads_contratos")
os.makedirs(UPLOAD_FOLDER_CONTRATOS, exist_ok=True)
app.config["UPLOAD_FOLDER_CONTRATOS"] = UPLOAD_FOLDER_CONTRATOS
ALLOWED_CONTRACT_EXTENSIONS = {'pdf'}

def allowed_contract(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_CONTRACT_EXTENSIONS

UPLOAD_FOLDER_HABILITACOES = os.path.join(os.getcwd(), "uploads_habilitacoes")
os.makedirs(UPLOAD_FOLDER_HABILITACOES, exist_ok=True)
app.config["UPLOAD_FOLDER_HABILITACOES"] = UPLOAD_FOLDER_HABILITACOES
ALLOWED_HAB_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg'}

def allowed_habilitacao(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_HAB_EXTENSIONS

# Inicializa banco
init_app(app)

# ================= ROTAS =====================

@app.route("/")
def home():
    if "user_id" not in session:
        return redirect(url_for("login"))
    return redirect(url_for("dashboard"))

# ---------- LOGIN ----------
@app.route("/login", methods=["GET", "POST"])
def login():
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
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


# ---------- DASHBOARD ----------
@app.route("/dashboard")
def dashboard():
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

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


# ---------- MOTOS ----------
@app.route("/motos", methods=["GET", "POST"])
def motos():
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    if request.method == "POST":
        placa = request.form["placa"]
        modelo = request.form["modelo"]
        ano = request.form["ano"]
        cur.execute(
            "INSERT INTO motos (placa, modelo, ano) VALUES (%s,%s,%s)",
            (placa, modelo, ano)
        )
        conn.commit()
        return redirect(url_for("motos"))

    cur.execute("SELECT * FROM motos")
    motos = cur.fetchall()
    cur.close()
    return render_template("motos.html", motos=motos)


# ---------- EDITAR MOTO ----------
@app.route("/motos/<int:id>/editar", methods=["GET", "POST"])
def editar_moto(id):
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    if request.method == "POST":
        placa = request.form["placa"]
        modelo = request.form["modelo"]
        ano = request.form["ano"]

        if "imagem" in request.files and request.files["imagem"].filename != "":
            file = request.files["imagem"]
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file_path = os.path.join(app.config["UPLOAD_FOLDER_MOTOS"], filename)
                file.save(file_path)

                # deleta imagem antiga
                cur.execute("SELECT imagem FROM motos WHERE id=%s", (id,))
                antiga = cur.fetchone()
                if antiga and antiga["imagem"]:
                    old_path = os.path.join(app.config["UPLOAD_FOLDER_MOTOS"], antiga["imagem"])
                    if os.path.exists(old_path):
                        os.remove(old_path)

                cur.execute("""
                    UPDATE motos SET placa=%s, modelo=%s, ano=%s, imagem=%s WHERE id=%s
                """, (placa, modelo, ano, filename, id))
        else:
            cur.execute("""
                UPDATE motos SET placa=%s, modelo=%s, ano=%s WHERE id=%s
            """, (placa, modelo, ano, id))

        conn.commit()
        cur.close()
        flash("Moto atualizada com sucesso!", "success")
        return redirect(url_for("motos"))

    cur.execute("SELECT * FROM motos WHERE id=%s", (id,))
    moto = cur.fetchone()
    cur.close()
    return render_template("editar_moto.html", moto=moto)


# ---------- CLIENTES ----------
@app.route("/clientes", methods=["GET", "POST"])
def clientes():
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    if request.method == "POST":
        nome = request.form["nome"]
        email = request.form["email"]
        telefone = request.form["telefone"]
        cpf = request.form.get("cpf")
        endereco = request.form.get("endereco")
        data_nascimento = request.form.get("data_nascimento")
        observacoes = request.form.get("observacoes")

        cur.execute("""
            INSERT INTO clientes (nome, email, telefone, cpf, endereco, data_nascimento, observacoes) 
            VALUES (%s,%s,%s,%s,%s,%s,%s)
        """, (nome, email, telefone, cpf, endereco, data_nascimento, observacoes))
        conn.commit()
        return redirect(url_for("clientes"))

    cur.execute("SELECT * FROM clientes")
    clientes = cur.fetchall()
    cur.close()
    return render_template("clientes.html", clientes=clientes)


# ---------- EDITAR CLIENTE ----------
@app.route("/clientes/<int:id>/editar", methods=["GET", "POST"])
def editar_cliente(id):
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    if request.method == "POST":
        nome = request.form["nome"]
        email = request.form["email"]
        telefone = request.form["telefone"]
        cpf = request.form.get("cpf")
        endereco = request.form.get("endereco")
        data_nascimento = request.form.get("data_nascimento")
        observacoes = request.form.get("observacoes")

        if "habilitacao" in request.files and request.files["habilitacao"].filename != "":
            file = request.files["habilitacao"]
            if file and allowed_habilitacao(file.filename):
                filename = secure_filename(file.filename)
                file_path = os.path.join(app.config["UPLOAD_FOLDER_HABILITACOES"], filename)
                file.save(file_path)

                # deleta habilitação antiga
                cur.execute("SELECT habilitacao_arquivo FROM clientes WHERE id=%s", (id,))
                antiga = cur.fetchone()
                if antiga and antiga["habilitacao_arquivo"]:
                    old_path = os.path.join(app.config["UPLOAD_FOLDER_HABILITACOES"], antiga["habilitacao_arquivo"])
                    if os.path.exists(old_path):
                        os.remove(old_path)

                cur.execute("""
                    UPDATE clientes SET nome=%s, email=%s, telefone=%s, cpf=%s, endereco=%s, 
                        data_nascimento=%s, observacoes=%s, habilitacao_arquivo=%s
                    WHERE id=%s
                """, (nome, email, telefone, cpf, endereco, data_nascimento, observacoes, filename, id))
        else:
            cur.execute("""
                UPDATE clientes SET nome=%s, email=%s, telefone=%s, cpf=%s, endereco=%s, 
                    data_nascimento=%s, observacoes=%s
                WHERE id=%s
            """, (nome, email, telefone, cpf, endereco, data_nascimento, observacoes, id))

        conn.commit()
        cur.close()
        flash("Cliente atualizado com sucesso!", "success")
        return redirect(url_for("clientes"))

    cur.execute("SELECT * FROM clientes WHERE id=%s", (id,))
    cliente = cur.fetchone()
    cur.close()
    return render_template("editar_cliente.html", cliente=cliente)

# (demais rotas de locações e serviços permanecem como você já tinha, incluindo contrato.pdf)

# ---------- Rotas de arquivos ----------
@app.route('/uploads_motos/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER_MOTOS'], filename)

@app.route('/uploads_contratos/<path:filename>')
def uploaded_contract(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER_CONTRATOS'], filename)

@app.route('/uploads_habilitacoes/<path:filename>')
def uploaded_habilitacao(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER_HABILITACOES'], filename)

# ---------- Run ----------
if __name__ == "__main__":
    app.run(debug=True)