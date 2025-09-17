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

# 🔹 Configuração para upload de habilitação dos clientes (pdf/jpg/png)
UPLOAD_FOLDER_HABILITACOES = os.path.join(os.getcwd(), "uploads_habilitacoes")
os.makedirs(UPLOAD_FOLDER_HABILITACOES, exist_ok=True)
app.config["UPLOAD_FOLDER_HABILITACOES"] = UPLOAD_FOLDER_HABILITACOES
ALLOWED_HAB_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg'}

def allowed_habilitacao(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_HAB_EXTENSIONS

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


# MOTOS
@app.route("/motos", methods=["GET", "POST"])
def motos():
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
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


# EDITAR MOTO
@app.route("/motos/<int:id>/editar", methods=["GET", "POST"])
def editar_moto(id):
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    if request.method == "POST":
        placa = request.form["placa"]
        modelo = request.form["modelo"]
        ano = request.form["ano"]
        
        cur.execute("""
            UPDATE motos
            SET placa=%s, modelo=%s, ano=%s
            WHERE id=%s
        """, (placa, modelo, ano, id))
        conn.commit()
        cur.close()
        
        flash("Moto atualizada com sucesso!", "success")
        return redirect(url_for("motos"))

    cur.execute("SELECT * FROM motos WHERE id=%s", (id,))
    moto = cur.fetchone()
    cur.close()
    return render_template("editar_moto.html", moto=moto)


# CLIENTES (cadastro e listagem)
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


# EDITAR CLIENTE
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

        cur.execute("""
            UPDATE clientes
            SET nome=%s, email=%s, telefone=%s, cpf=%s, endereco=%s, data_nascimento=%s, observacoes=%s
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


# HABILITAÇÃO DO CLIENTE
@app.route("/clientes/<int:id>/habilitacao", methods=["GET", "POST"])
def cliente_habilitacao(id):
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    if request.method == "POST":
        file = request.files.get("habilitacao")
        if file and allowed_habilitacao(file.filename):
            # Deleta antiga (se houver)
            cur.execute("SELECT habilitacao_arquivo FROM clientes WHERE id=%s", (id,))
            antigo = cur.fetchone()
            if antigo and antigo["habilitacao_arquivo"]:
                old_path = os.path.join(app.config["UPLOAD_FOLDER_HABILITACOES"], antigo["habilitacao_arquivo"])
                if os.path.exists(old_path):
                    os.remove(old_path)

            # Salva nova
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config["UPLOAD_FOLDER_HABILITACOES"], filename)
            file.save(file_path)

            cur.execute("UPDATE clientes SET habilitacao_arquivo=%s WHERE id=%s", (filename, id))
            conn.commit()
            flash("Habilitação anexada com sucesso!", "success")

    cur.execute("SELECT id, nome, habilitacao_arquivo FROM clientes WHERE id=%s", (id,))
    cliente = cur.fetchone()
    cur.close()

    return render_template("cliente_habilitacao.html", cliente=cliente)


# EXCLUIR HABILITAÇÃO DO CLIENTE
@app.route("/clientes/<int:id>/habilitacao/excluir", methods=["POST"])
def excluir_habilitacao(id):
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute("SELECT habilitacao_arquivo FROM clientes WHERE id=%s", (id,))
    cliente = cur.fetchone()

    if cliente and cliente["habilitacao_arquivo"]:
        filepath = os.path.join(app.config["UPLOAD_FOLDER_HABILITACOES"], cliente["habilitacao_arquivo"])
        if os.path.exists(filepath):
            os.remove(filepath)

        cur.execute("UPDATE clientes SET habilitacao_arquivo=NULL WHERE id=%s", (id,))
        conn.commit()

    cur.close()
    flash("Habilitação removida com sucesso!", "info")
    return redirect(url_for("cliente_habilitacao", id=id))


# IMAGENS DAS MOTOS
@app.route("/motos/<int:moto_id>/imagens", methods=["GET", "POST"])
def moto_imagens(moto_id):
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

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
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

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

# UPLOAD DOCUMENTO DA MOTO
UPLOAD_FOLDER_DOCUMENTOS = os.path.join(os.getcwd(), "uploads_documentos_motos")
os.makedirs(UPLOAD_FOLDER_DOCUMENTOS, exist_ok=True)
app.config["UPLOAD_FOLDER_DOCUMENTOS"] = UPLOAD_FOLDER_DOCUMENTOS
ALLOWED_DOC_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg'}

def allowed_documento(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_DOC_EXTENSIONS

@app.route("/motos/<int:moto_id>/documento", methods=["GET", "POST"])
def moto_documento(moto_id):
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    if request.method == "POST":
        file = request.files.get("documento")
        if file and allowed_documento(file.filename):
            # Deleta antigo (se houver)
            cur.execute("SELECT documento_arquivo FROM motos WHERE id=%s", (moto_id,))
            antigo = cur.fetchone()
            if antigo and antigo["documento_arquivo"]:
                old_path = os.path.join(app.config["UPLOAD_FOLDER_DOCUMENTOS"], antigo["documento_arquivo"])
                if os.path.exists(old_path):
                    os.remove(old_path)

            # Salva novo
            filename = secure_filename(file.filename)
            path = os.path.join(app.config["UPLOAD_FOLDER_DOCUMENTOS"], filename)
            file.save(path)

            cur.execute("UPDATE motos SET documento_arquivo=%s WHERE id=%s", (filename, moto_id))
            conn.commit()
            flash("Documento da moto anexado com sucesso!", "success")

    cur.execute("SELECT * FROM motos WHERE id=%s", (moto_id,))
    moto = cur.fetchone()
    cur.close()

    return render_template("moto_documento.html", moto=moto)


@app.route("/motos/<int:moto_id>/documento/excluir", methods=["POST"])
def excluir_documento_moto(moto_id):
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute("SELECT documento_arquivo FROM motos WHERE id=%s", (moto_id,))
    moto = cur.fetchone()

    if moto and moto["documento_arquivo"]:
        filepath = os.path.join(app.config["UPLOAD_FOLDER_DOCUMENTOS"], moto["documento_arquivo"])
        if os.path.exists(filepath):
            os.remove(filepath)

        cur.execute("UPDATE motos SET documento_arquivo=NULL WHERE id=%s", (moto_id,))
        conn.commit()

    cur.close()
    flash("Documento da moto removido com sucesso!", "info")
    return redirect(url_for("moto_documento", moto_id=moto_id))


# LOCAÇÕES
@app.route("/locacoes", methods=["GET", "POST"])
def locacoes():
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    if request.method == "POST":
        cliente_id = request.form["cliente_id"]
        moto_id = request.form["moto_id"]
        data_inicio = request.form["data_inicio"]
        observacoes = request.form.get("observacoes")

        # Upload do contrato PDF
        contrato_pdf = None
        if "contrato_pdf" in request.files:
            file = request.files["contrato_pdf"]
            if file and allowed_contract(file.filename):
                filename = secure_filename(file.filename)
                contrato_path = os.path.join(app.config["UPLOAD_FOLDER_CONTRATOS"], filename)
                file.save(contrato_path)
                contrato_pdf = filename

        cur.execute("""
            INSERT INTO locacoes (cliente_id, moto_id, data_inicio, observacoes, contrato_pdf) 
            VALUES (%s,%s,%s,%s,%s)
        """, (cliente_id, moto_id, data_inicio, observacoes, contrato_pdf))

        cur.execute("UPDATE motos SET disponivel=FALSE WHERE id=%s", (moto_id,))
        conn.commit()
        return redirect(url_for("locacoes"))

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

    cur.execute("SELECT id, nome FROM clientes")
    clientes = cur.fetchall()

    cur.execute("SELECT id, modelo, placa FROM motos WHERE disponivel=TRUE")
    motos = cur.fetchall()

    cur.close()
    return render_template("locacoes.html", locacoes=locacoes, clientes=clientes, motos=motos)

# ---------- LOCAÇÕES CANCELADAS ----------
@app.route("/locacoes/canceladas")
def locacoes_canceladas():
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute("""
        SELECT l.id, 
               c.nome AS cliente_nome, 
               m.modelo AS moto_modelo, 
               m.placa AS moto_placa,
               l.data_inicio, 
               l.data_fim, 
               l.observacoes,
               l.contrato_pdf
        FROM locacoes l
        JOIN clientes c ON l.cliente_id = c.id
        JOIN motos m ON l.moto_id = m.id
        WHERE l.cancelado = TRUE
        ORDER BY l.data_inicio DESC
    """)
    canceladas = cur.fetchall()
    cur.close()

    return render_template("locacoes_canceladas.html", canceladas=canceladas)


# EDITAR LOCAÇÃO (com contrato PDF)
@app.route("/locacoes/<int:id>/editar", methods=["GET", "POST"])
def editar_locacao(id):
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    if request.method == "POST":
        data_inicio = request.form["data_inicio"]
        data_fim = request.form.get("data_fim")
        observacoes = request.form.get("observacoes")

        contrato_pdf = None
        if "contrato_pdf" in request.files:
            file =request.files["contrato_pdf"]
            if file and allowed_contract(file.filename):
                filename = secure_filename(file.filename)
                contrato_path = os.path.join(app.config["UPLOAD_FOLDER_CONTRATOS"], filename)
                file.save(contrato_path)
                contrato_pdf = filename

                # Deleta contrato antigo
                cur.execute("SELECT contrato_pdf FROM locacoes WHERE id=%s", (id,))
                antigo = cur.fetchone()
                if antigo and antigo["contrato_pdf"]:
                    old_path = os.path.join(app.config["UPLOAD_FOLDER_CONTRATOS"], antigo["contrato_pdf"])
                    if os.path.exists(old_path):
                        os.remove(old_path)

                cur.execute("""
                    UPDATE locacoes
                    SET data_inicio=%s, data_fim=%s, observacoes=%s, contrato_pdf=%s
                    WHERE id=%s
                """, (data_inicio, data_fim, observacoes, contrato_pdf, id))
            else:
                cur.execute("""
                    UPDATE locacoes
                    SET data_inicio=%s, data_fim=%s, observacoes=%s
                    WHERE id=%s
                """, (data_inicio, data_fim, observacoes, id))
        else:
            cur.execute("""
                UPDATE locacoes
                SET data_inicio=%s, data_fim=%s, observacoes=%s
                WHERE id=%s
            """, (data_inicio, data_fim, observacoes, id))

        conn.commit()
        cur.close()
        flash("Locação atualizada com sucesso!", "success")
        return redirect(url_for("locacoes"))

    cur.execute("""
        SELECT l.*, c.nome as cliente_nome, m.modelo as moto_modelo, m.placa as moto_placa
        FROM locacoes l
        JOIN clientes c ON l.cliente_id = c.id
        JOIN motos m ON l.moto_id = m.id
        WHERE l.id=%s
    """, (id,))
    locacao = cur.fetchone()
    cur.close()

    if not locacao:
        flash("Locação não encontrada.", "warning")
        return redirect(url_for("locacoes"))

    return render_template("editar_locacao.html", locacao=locacao)


@app.route("/locacoes/<int:id>/cancelar", methods=["POST"])
def cancelar_locacao(id):
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute("SELECT moto_id FROM locacoes WHERE id = %s", (id,))
    locacao = cur.fetchone()
    if locacao:
        moto_id = locacao["moto_id"]
        cur.execute("UPDATE locacoes SET cancelado = TRUE WHERE id = %s", (id,))
        cur.execute("UPDATE motos SET disponivel = TRUE WHERE id = %s", (moto_id,))
        conn.commit()

    cur.close()
    return redirect(url_for("locacoes"))


# SERVIÇOS NAS LOCAÇÕES
@app.route("/locacoes/<int:locacao_id>/servicos", methods=["GET", "POST"])
def servicos_locacao(locacao_id):
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    if request.method == "POST":
        descricao = request.form["descricao"]
        valor = request.form.get("valor") or 0
        cur.execute("""
            INSERT INTO servicos_locacao (locacao_id, descricao, valor) 
            VALUES (%s, %s, %s)
        """, (locacao_id, descricao, valor))
        conn.commit()

    cur.execute("""
        SELECT l.id, c.nome, m.modelo, m.placa
        FROM locacoes l
        JOIN clientes c ON l.cliente_id = c.id
        JOIN motos m ON l.moto_id = m.id
        WHERE l.id = %s
    """, (locacao_id,))
    locacao = cur.fetchone()

    cur.execute("""
        SELECT id, descricao, valor, data_servico
        FROM servicos_locacao
        WHERE locacao_id = %s
        ORDER BY data_servico DESC
    """, (locacao_id,))
    servicos = cur.fetchall()

    cur.close()
    return render_template("servicos_locacao.html", locacao=locacao, servicos=servicos)


# ROTAS DE SERVIR ARQUIVOS
@app.route('/uploads_motos/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER_MOTOS'], filename)

@app.route('/uploads_contratos/<path:filename>')
def uploaded_contract(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER_CONTRATOS'], filename)

@app.route('/uploads_habilitacoes/<path:filename>')
def uploaded_habilitacao(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER_HABILITACOES'], filename)

@app.route('/uploads_documentos_motos/<path:filename>')
def uploaded_documento(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER_DOCUMENTOS'], filename)


# ---------- Run ----------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))  # ✅ Render exige porta dinâmica
    app.run(host="0.0.0.0", port=port, debug=True)