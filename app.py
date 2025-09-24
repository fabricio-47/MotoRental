import os
import requests
import hmac
import hashlib
from flask import Flask, render_template, request, redirect, url_for, flash, session, send_from_directory, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import psycopg2.extras
from database import get_db, init_app
from datetime import datetime

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-key")
app.config["DATABASE_URL"] = os.environ.get("DATABASE_URL")

# 🔒 Base do Render Disk (persistente)
BASE_UPLOAD = "/var/data"

# 🔹 Configuração para uploads de imagens de motos
UPLOAD_FOLDER_MOTOS = os.path.join(BASE_UPLOAD, "uploads_motos")
os.makedirs(UPLOAD_FOLDER_MOTOS, exist_ok=True)
app.config["UPLOAD_FOLDER_MOTOS"] = UPLOAD_FOLDER_MOTOS
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# 🔹 Configuração para upload de contratos (PDF)
UPLOAD_FOLDER_CONTRATOS = os.path.join(BASE_UPLOAD, "uploads_contratos")
os.makedirs(UPLOAD_FOLDER_CONTRATOS, exist_ok=True)
app.config["UPLOAD_FOLDER_CONTRATOS"] = UPLOAD_FOLDER_CONTRATOS
ALLOWED_CONTRACT_EXTENSIONS = {'pdf'}

def allowed_contract(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_CONTRACT_EXTENSIONS

# 🔹 Configuração para upload de habilitação dos clientes (pdf/jpg/png)
UPLOAD_FOLDER_HABILITACOES = os.path.join(BASE_UPLOAD, "uploads_habilitacoes")
os.makedirs(UPLOAD_FOLDER_HABILITACOES, exist_ok=True)
app.config["UPLOAD_FOLDER_HABILITACOES"] = UPLOAD_FOLDER_HABILITACOES
ALLOWED_HAB_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg'}

def allowed_habilitacao(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_HAB_EXTENSIONS

# 🔹 Configuração para upload de documentos das motos
UPLOAD_FOLDER_DOCUMENTOS = os.path.join(BASE_UPLOAD, "uploads_documentos_motos")
os.makedirs(UPLOAD_FOLDER_DOCUMENTOS, exist_ok=True)
app.config["UPLOAD_FOLDER_DOCUMENTOS"] = UPLOAD_FOLDER_DOCUMENTOS
ALLOWED_DOC_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg'}

def allowed_documento(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_DOC_EXTENSIONS

# Inicializa funções de banco
init_app(app)

# ---- ASAAS ----
ASAAS_API_KEY = os.environ.get("ASAAS_API_KEY")
ASAAS_BASE_URL = os.environ.get("ASAAS_BASE_URL", "https://sandbox.asaas.com/api/v3")
app.config["ASAAS_WEBHOOK_SECRET"] = os.environ.get("ASAAS_WEBHOOK_SECRET")

asaas_headers = {
    "accept": "application/json",
    "content-type": "application/json",
    "access_token": ASAAS_API_KEY
}

# Frequências de pagamento permitidas
FREQ_ALLOWED = {"semanal", "quinzenal", "mensal", "trimestral"}

def criar_cliente_asaas(nome, email, cpf, telefone):
    payload = {"name": nome, "email": email, "cpfCnpj": cpf, "mobilePhone": telefone}
    r = requests.post(f"{ASAAS_BASE_URL}/customers", headers=asaas_headers, json=payload)
    return r.json()

def criar_cobranca_asaas(customer_id, valor, vencimento, descricao="Locação de Moto"):
    payload = {
        "customer": customer_id,
        "billingType": "BOLETO",
        "dueDate": vencimento,
        "value": valor,
        "description": descricao
    }
    r = requests.post(f"{ASAAS_BASE_URL}/payments", headers=asaas_headers, json=payload)
    return r.json()

def buscar_cliente_asaas(cpf=None, email=None):
    params = {}
    if cpf:
        params["cpfCnpj"] = cpf
    if email:
        params["email"] = email

    r = requests.get(f"{ASAAS_BASE_URL}/customers", headers=asaas_headers, params=params)
    if r.status_code == 200:
        data = r.json()
        if data.get("data") and len(data["data"]) > 0:
            return data["data"][0]  # Retorna o primeiro cliente encontrado
    return None

def buscar_pagamentos_asaas(customer_id):
    """Busca todos os pagamentos de um cliente no Asaas"""
    try:
        params = {"customer": customer_id}
        r = requests.get(f"{ASAAS_BASE_URL}/payments", headers=asaas_headers, params=params)
        if r.status_code == 200:
            return r.json().get("data", [])
    except Exception as e:
        print(f"Erro ao buscar pagamentos no Asaas: {e}")
    return []

def sincronizar_boletos_locacao(locacao_id):
    """
    Sincroniza os boletos de uma locação específica com o Asaas
    Busca todos os pagamentos do cliente no Asaas e atualiza a tabela boletos
    """
    try:
        with get_db().cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            # Buscar dados da locação e cliente
            cur.execute("""
                SELECT l.id, l.cliente_id, c.asaas_id, c.nome as cliente_nome
                FROM locacoes l
                JOIN clientes c ON l.cliente_id = c.id
                WHERE l.id = %s
            """, (locacao_id,))
            locacao = cur.fetchone()

            if not locacao or not locacao["asaas_id"]:
                return False

            # Buscar pagamentos no Asaas
            pagamentos_asaas = buscar_pagamentos_asaas(locacao["asaas_id"])

            for pagamento in pagamentos_asaas:
                payment_id = pagamento.get("id")
                if not payment_id:
                    continue

                # Verificar se o boleto já existe na tabela
                cur.execute("SELECT id FROM boletos WHERE asaas_payment_id = %s", (payment_id,))
                boleto_existente = cur.fetchone()

                if boleto_existente:
                    # Atualizar boleto existente
                    cur.execute("""
                        UPDATE boletos SET
                            status = %s,
                            valor = %s,
                            data_vencimento = %s,
                            data_pagamento = %s,
                            valor_pago = %s,
                            boleto_url = %s,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE asaas_payment_id = %s
                    """, (
                        pagamento.get("status"),
                        pagamento.get("value"),
                        pagamento.get("dueDate"),
                        pagamento.get("paymentDate"),
                        pagamento.get("paidValue"),
                        pagamento.get("bankSlipUrl"),
                        payment_id
                    ))
                else:
                    # Inserir novo boleto
                    cur.execute("""
                        INSERT INTO boletos (
                            locacao_id, asaas_payment_id, status, valor,
                            data_vencimento, data_pagamento, valor_pago,
                            boleto_url, descricao
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        locacao_id,
                        payment_id,
                        pagamento.get("status"),
                        pagamento.get("value"),
                        pagamento.get("dueDate"),
                        pagamento.get("paymentDate"),
                        pagamento.get("paidValue"),
                        pagamento.get("bankSlipUrl"),
                        pagamento.get("description", "Locação de Moto")
                    ))

            get_db().commit()
            return True

    except Exception as e:
        get_db().rollback()
        print(f"Erro ao sincronizar boletos: {e}")
        return False

# === Helpers para cancelamento no Asaas ===

def cancelar_assinatura_asaas(subscription_id: str):
    """
    Cancela uma assinatura no Asaas.
    Retorna (ok: bool, mensagem: str).
    """
    try:
        r = requests.delete(f"{ASAAS_BASE_URL}/subscriptions/{subscription_id}", headers=asaas_headers, timeout=15)
        if r.status_code in (200, 204):
            return True, "Assinatura cancelada."
        data = {}
        try:
            data = r.json()
        except Exception:
            pass
        msg = data.get("errors", [{}])[0].get("description") if isinstance(data, dict) else r.text
        return False, f"Erro ao cancelar assinatura: {msg or r.text}"
    except Exception as ex:
        return False, f"Exceção ao cancelar assinatura: {ex}"

def cancelar_pagamento_asaas(payment_id: str):
    """
    Cancela um pagamento pendente no Asaas.
    Retorna (ok: bool, mensagem: str).
    """
    try:
        r = requests.delete(f"{ASAAS_BASE_URL}/payments/{payment_id}", headers=asaas_headers, timeout=15)
        if r.status_code in (200, 204):
            return True, "Pagamento cancelado."
        data = {}
        try:
            data = r.json()
        except Exception:
            pass
        msg = data.get("errors", [{}])[0].get("description") if isinstance(data, dict) else r.text
        return False, f"Erro ao cancelar pagamento: {msg or r.text}"
    except Exception as ex:
        return False, f"Exceção ao cancelar pagamento: {ex}"

# ---- ROTAS ----
@app.route("/")
def home():
    if "user_id" not in session:
        return redirect(url_for("login"))
    return redirect(url_for("dashboard"))

# LOGIN
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        senha = request.form["senha"]

        with get_db().cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT id, username, email, senha FROM usuarios WHERE email = %s", (email,))
            user = cur.fetchone()

            if user and check_password_hash(user["senha"], senha):
                session["user_id"] = user["id"]
                session["user_email"] = user["email"]
                session["username"] = user["username"]
                return redirect(url_for("dashboard"))
            else:
                flash("E-mail ou senha inválidos", "error")

    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/dashboard")
def dashboard():
    with get_db().cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("SELECT COUNT(*) AS total FROM clientes")
        total_clientes = cur.fetchone()["total"]

        cur.execute("SELECT COUNT(*) AS total FROM motos")
        total_motos = cur.fetchone()["total"]

        cur.execute("SELECT COUNT(*) AS total FROM locacoes WHERE cancelado = FALSE")
        locacoes_ativas = cur.fetchone()["total"]

        cur.execute("SELECT COUNT(*) AS total FROM locacoes WHERE cancelado = TRUE")
        locacoes_canceladas = cur.fetchone()["total"]

        return render_template(
            "dashboard.html",
            total_clientes=total_clientes,
            total_motos=total_motos,
            locacoes_ativas=locacoes_ativas,
            locacoes_canceladas=locacoes_canceladas
        )

# === CLIENTES (CRUD + Asaas + Habilitação) ===

@app.route("/clientes", methods=["GET", "POST"])
def clientes():
    if request.method == "POST":
        nome = request.form["nome"].strip()
        email = request.form["email"].strip().lower()
        telefone = request.form["telefone"].strip()
        cpf = (request.form.get("cpf") or "").strip()
        endereco = (request.form.get("endereco") or "").strip()
        data_nascimento = request.form.get("data_nascimento") or None
        observacoes = (request.form.get("observacoes") or "").strip()

        try:
            with get_db().cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                # Validar duplicidade local
                cur.execute("SELECT id FROM clientes WHERE email=%s OR cpf=%s", (email, cpf))
                if cur.fetchone():
                    flash("Já existe cliente com este e-mail ou CPF.", "error")
                    return redirect(url_for("clientes"))

                # Verificar se cliente já existe no Asaas
                cliente_asaas_existente = buscar_cliente_asaas(cpf=cpf, email=email)
                if cliente_asaas_existente:
                    asaas_id = cliente_asaas_existente.get("id")
                else:
                    asaas_cliente = criar_cliente_asaas(nome, email, cpf, telefone)
                    if "errors" in asaas_cliente:
                        msg = asaas_cliente["errors"][0].get("description", "Erro ao criar cliente no Asaas.")
                        flash(f"Erro no Asaas: {msg}", "error")
                        return redirect(url_for("clientes"))
                    asaas_id = asaas_cliente.get("id")

                # Inserir localmente
                cur.execute("""
                    INSERT INTO clientes (nome, email, telefone, cpf, endereco, data_nascimento, observacoes, asaas_id)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                """, (nome, email, telefone, cpf, endereco, data_nascimento, observacoes, asaas_id))
                get_db().commit()

                flash("Cliente cadastrado com sucesso!", "success")
        except Exception as e:
            get_db().rollback()
            flash(f"Erro ao cadastrar cliente: {e}", "error")

        return redirect(url_for("clientes"))

    # GET
    with get_db().cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("SELECT * FROM clientes ORDER BY id DESC")
        clientes = cur.fetchall()
        return render_template("clientes.html", clientes=clientes)

@app.route("/clientes/<int:id>/editar", methods=["GET", "POST"])
def editar_cliente(id):
    with get_db().cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        if request.method == "POST":
            nome = request.form["nome"].strip()
            email = request.form["email"].strip().lower()
            telefone = request.form["telefone"].strip()
            cpf = (request.form.get("cpf") or "").strip()
            endereco = (request.form.get("endereco") or "").strip()
            data_nascimento = request.form.get("data_nascimento") or None
            observacoes = (request.form.get("observacoes") or "").strip()

            try:
                # Evitar duplicidade ao editar (outro registro com mesmo email/cpf)
                cur.execute("""
                    SELECT id FROM clientes
                    WHERE (email=%s OR cpf=%s) AND id <> %s
                """, (email, cpf, id))
                if cur.fetchone():
                    flash("Outro cliente já utiliza este e-mail ou CPF.", "error")
                    return redirect(url_for("editar_cliente", id=id))

                cur.execute("""
                    UPDATE clientes
                    SET nome=%s, email=%s, telefone=%s, cpf=%s, endereco=%s,
                        data_nascimento=%s, observacoes=%s
                    WHERE id=%s
                """, (nome, email, telefone, cpf, endereco, data_nascimento, observacoes, id))
                get_db().commit()
                flash("Cliente atualizado com sucesso!", "success")
            except Exception as e:
                get_db().rollback()
                flash(f"Erro ao atualizar cliente: {e}", "error")

            return redirect(url_for("clientes"))

        # GET: buscar cliente
        cur.execute("SELECT * FROM clientes WHERE id=%s", (id,))
        cliente = cur.fetchone()
        if not cliente:
            flash("Cliente não encontrado!", "error")
            return redirect(url_for("clientes"))

        # Buscar boletos desse cliente (mesmo de locações canceladas)
        cur.execute("""
            SELECT b.*, l.cancelado
            FROM boletos b
            JOIN locacoes l ON b.locacao_id = l.id
            WHERE l.cliente_id = %s
            ORDER BY b.data_vencimento DESC
        """, (id,))
        boletos_cliente = cur.fetchall()

        return render_template("editar_cliente.html",
                             cliente=cliente,
                             boletos_cliente=boletos_cliente)

@app.route("/clientes/<int:id>/excluir", methods=["POST"])
def excluir_cliente(id):
    try:
        with get_db().cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            # Verifica se o cliente tem locações ativas
            cur.execute("SELECT id FROM locacoes WHERE cliente_id=%s AND cancelado=FALSE", (id,))
            if cur.fetchone():
                flash("Não é possível excluir cliente com locações ativas.", "error")
                return redirect(url_for("clientes"))

            # remover arquivo de habilitação se houver
            cur.execute("SELECT habilitacao_arquivo FROM clientes WHERE id=%s", (id,))
            cliente = cur.fetchone()
            if not cliente:
                flash("Cliente não encontrado.", "error")
                return redirect(url_for("clientes"))

            if cliente["habilitacao_arquivo"]:
                filepath = os.path.join(app.config["UPLOAD_FOLDER_HABILITACOES"], cliente["habilitacao_arquivo"])
                if os.path.exists(filepath):
                    os.remove(filepath)

            # excluir cliente
            cur.execute("DELETE FROM clientes WHERE id=%s", (id,))
            get_db().commit()
            flash("Cliente excluído com sucesso!", "info")
    except Exception as e:
        get_db().rollback()
        flash(f"Erro ao excluir cliente: {e}", "error")

    return redirect(url_for("clientes"))

# ==== HABILITAÇÃO DO CLIENTE ====

@app.route("/clientes/<int:id>/habilitacao", methods=["GET", "POST"])
def cliente_habilitacao(id):
    with get_db().cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        if request.method == "POST":
            file = request.files.get("habilitacao")
            if not file or not allowed_habilitacao(file.filename):
                flash("Arquivo inválido. Envie PDF, PNG ou JPG.", "error")
                return redirect(url_for("cliente_habilitacao", id=id))

            # Apaga arquivo antigo se existir
            cur.execute("SELECT habilitacao_arquivo FROM clientes WHERE id=%s", (id,))
            antigo = cur.fetchone()
            if not antigo:
                flash("Cliente não encontrado.", "error")
                return redirect(url_for("clientes"))

            if antigo["habilitacao_arquivo"]:
                old_path = os.path.join(app.config["UPLOAD_FOLDER_HABILITACOES"], antigo["habilitacao_arquivo"])
                if os.path.exists(old_path):
                    os.remove(old_path)

            # Salva novo
            filename = secure_filename(file.filename)
            # Opcional: prefixar com ID para evitar colisões
            filename = f"cliente_{id}__{filename}"
            file_path = os.path.join(app.config["UPLOAD_FOLDER_HABILITACOES"], filename)
            file.save(file_path)

            try:
                cur.execute("UPDATE clientes SET habilitacao_arquivo=%s WHERE id=%s", (filename, id))
                get_db().commit()
                flash("Habilitação anexada com sucesso!", "success")
            except Exception as e:
                get_db().rollback()
                # rollback do arquivo salvo em caso de erro
                if os.path.exists(file_path):
                    os.remove(file_path)
                flash(f"Erro ao salvar habilitação: {e}", "error")

        # GET (ou após POST) → exibir
        cur.execute("SELECT id, nome, habilitacao_arquivo FROM clientes WHERE id=%s", (id,))
        cliente = cur.fetchone()
        if not cliente:
            flash("Cliente não encontrado.", "error")
            return redirect(url_for("clientes"))

        return render_template("cliente_habilitacao.html", cliente=cliente)

@app.route("/clientes/<int:id>/habilitacao/excluir", methods=["POST"])
def excluir_habilitacao(id):
    try:
        with get_db().cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT habilitacao_arquivo FROM clientes WHERE id=%s", (id,))
            cliente = cur.fetchone()
            if not cliente:
                flash("Cliente não encontrado.", "error")
                return redirect(url_for("clientes"))

            if cliente["habilitacao_arquivo"]:
                filepath = os.path.join(app.config["UPLOAD_FOLDER_HABILITACOES"], cliente["habilitacao_arquivo"])
                if os.path.exists(filepath):
                    os.remove(filepath)

            cur.execute("UPDATE clientes SET habilitacao_arquivo=NULL WHERE id=%s", (id,))
            get_db().commit()
            flash("Habilitação removida com sucesso!", "info")
    except Exception as e:
        get_db().rollback()
        flash(f"Erro ao remover habilitação: {e}", "error")

    return redirect(url_for("cliente_habilitacao", id=id))

# === MOTOS (CRUD + Imagens + Documento) ===

@app.route("/motos", methods=["GET", "POST"])
def motos():
    if request.method == "POST":
        placa = request.form["placa"].strip().upper()
        modelo = request.form["modelo"].strip()
        ano = (request.form.get("ano") or "").strip()

        try:
            with get_db().cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                # Validar duplicidade de placa
                cur.execute("SELECT id FROM motos WHERE placa=%s", (placa,))
                if cur.fetchone():
                    flash("Já existe uma moto cadastrada com esta placa.", "error")
                    return redirect(url_for("motos"))

                cur.execute(
                    "INSERT INTO motos (placa, modelo, ano, disponivel) VALUES (%s,%s,%s, TRUE)",
                    (placa, modelo, ano or None)
                )
                get_db().commit()
                flash("Moto cadastrada com sucesso!", "success")
        except Exception as e:
            get_db().rollback()
            flash(f"Erro ao cadastrar moto: {e}", "error")

        return redirect(url_for("motos"))

    # GET
    with get_db().cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("SELECT * FROM motos ORDER BY id DESC")
        motos = cur.fetchall()
        return render_template("motos.html", motos=motos)

@app.route("/motos/<int:id>/editar", methods=["GET", "POST"])
def editar_moto(id):
    with get_db().cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        if request.method == "POST":
            placa = request.form["placa"].strip().upper()
            modelo = request.form["modelo"].strip()
            ano = (request.form.get("ano") or "").strip()

            try:
                # Garante que outra moto não tenha a mesma placa
                cur.execute("SELECT id FROM motos WHERE placa=%s AND id<>%s", (placa, id))
                if cur.fetchone():
                    flash("Outra moto já utiliza esta placa.", "error")
                    return redirect(url_for("editar_moto", id=id))

                cur.execute("""
                    UPDATE motos
                    SET placa=%s, modelo=%s, ano=%s
                    WHERE id=%s
                """, (placa, modelo, ano or None, id))
                get_db().commit()
                flash("Moto atualizada com sucesso!", "success")
            except Exception as e:
                get_db().rollback()
                flash(f"Erro ao atualizar moto: {e}", "error")

            return redirect(url_for("motos"))

        # GET
        cur.execute("SELECT * FROM motos WHERE id=%s", (id,))
        moto = cur.fetchone()
        if not moto:
            flash("Moto não encontrada.", "error")
            return redirect(url_for("motos"))

        return render_template("editar_moto.html", moto=moto)

@app.route("/motos/<int:id>/excluir", methods=["POST"])
def excluir_moto(id):
    try:
        with get_db().cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            # Verifica se a moto tem locações ativas
            cur.execute("SELECT id FROM locacoes WHERE moto_id=%s AND cancelado=FALSE", (id,))
            if cur.fetchone():
                flash("Não é possível excluir moto com locações ativas.", "error")
                return redirect(url_for("motos"))

            # Buscar arquivos relacionados da moto
            cur.execute("""
                SELECT imagem, documento_arquivo
                FROM motos
                WHERE id=%s
            """, (id,))
            moto = cur.fetchone()
            if not moto:
                flash("Moto não encontrada.", "error")
                return redirect(url_for("motos"))

            # Remover arquivo de imagem da moto
            if moto["imagem"]:
                caminho_imagem = os.path.join(app.config["UPLOAD_FOLDER_MOTOS"], moto["imagem"])
                if os.path.exists(caminho_imagem):
                    os.remove(caminho_imagem)

            # Remover arquivo de documento da moto
            if moto["documento_arquivo"]:
                caminho_documento = os.path.join(app.config["UPLOAD_FOLDER_DOCUMENTOS"], moto["documento_arquivo"])
                if os.path.exists(caminho_documento):
                    os.remove(caminho_documento)

            # Se você tiver outras pastas/arquivos relacionados (ex: imagens múltiplas), remova aqui também
            # Exemplo para múltiplas imagens:
            cur.execute("SELECT arquivo FROM moto_imagens WHERE moto_id=%s", (id,))
            imagens = cur.fetchall()
            for img in imagens:
                caminho_img = os.path.join(app.config["UPLOAD_FOLDER_MOTOS"], img["arquivo"])
                if os.path.exists(caminho_img):
                    os.remove(caminho_img)

            # Excluir registros de imagens múltiplas da moto
            cur.execute("DELETE FROM moto_imagens WHERE moto_id=%s", (id,))

            # Excluir a moto
            cur.execute("DELETE FROM motos WHERE id=%s", (id,))
            get_db().commit()
            flash("Moto excluída com sucesso!", "info")
    except Exception as e:
        get_db().rollback()
        flash(f"Erro ao excluir moto: {e}", "error")

    return redirect(url_for("motos"))

# === IMAGENS DA MOTO ===

@app.route("/motos/<int:moto_id>/imagens", methods=["GET", "POST"])
def moto_imagens(moto_id):
    with get_db().cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        # Verifica se a moto existe (para evitar upload perdido)
        cur.execute("SELECT id, modelo, placa, ano FROM motos WHERE id=%s", (moto_id,))
        moto = cur.fetchone()
        if not moto:
            flash("Moto não encontrada.", "error")
            return redirect(url_for("motos"))

        if request.method == "POST":
            if "imagem" not in request.files:
                flash("Nenhum arquivo enviado.", "error")
                return redirect(url_for("moto_imagens", moto_id=moto_id))

            file = request.files["imagem"]
            if not file or not allowed_file(file.filename):
                flash("Arquivo inválido. Envie PNG ou JPG.", "error")
                return redirect(url_for("moto_imagens", moto_id=moto_id))

            filename = secure_filename(file.filename)
            # Prefixa com ID e contador se necessário para evitar colisão
            base, ext = os.path.splitext(filename)
            filename = f"moto_{moto_id}__{base}{ext}"
            save_path = os.path.join(app.config["UPLOAD_FOLDER_MOTOS"], filename)

            # Se já existir, incrementa sufixo
            if os.path.exists(save_path):
                i = 1
                while True:
                    candidate = f"moto_{moto_id}__{base}_{i}{ext}"
                    save_path = os.path.join(app.config["UPLOAD_FOLDER_MOTOS"], candidate)
                    if not os.path.exists(save_path):
                        filename = candidate
                        break
                    i += 1

            try:
                file.save(save_path)
                cur.execute("INSERT INTO moto_imagens (moto_id, arquivo) VALUES (%s, %s)", (moto_id, filename))
                get_db().commit()
                flash("Imagem enviada com sucesso!", "success")
            except Exception as e:
                get_db().rollback()
                # Se deu erro depois de salvar, tenta limpar
                if os.path.exists(save_path):
                    try:
                        os.remove(save_path)
                    except Exception:
                        pass
                flash(f"Erro ao salvar imagem: {e}", "error")

            return redirect(url_for("moto_imagens", moto_id=moto_id))

        # GET
        cur.execute("SELECT * FROM moto_imagens WHERE moto_id = %s ORDER BY data_upload DESC", (moto_id,))
        imagens = cur.fetchall()

        return render_template("moto_imagens.html", moto=moto, imagens=imagens)

@app.route("/motos/<int:moto_id>/imagens/<int:imagem_id>/excluir", methods=["POST"])
def excluir_imagem_moto(moto_id, imagem_id):
    try:
        with get_db().cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            # busca arquivo
            cur.execute("SELECT arquivo FROM moto_imagens WHERE id = %s AND moto_id = %s", (imagem_id, moto_id))
            imagem = cur.fetchone()
            if not imagem:
                flash("Imagem não encontrada.", "error")
                return redirect(url_for('moto_imagens', moto_id=moto_id))

            # remove do disco
            arquivo_path = os.path.join(app.config["UPLOAD_FOLDER_MOTOS"], imagem["arquivo"])
            if os.path.exists(arquivo_path):
                try:
                    os.remove(arquivo_path)
                except Exception:
                    pass

            # remove do banco
            cur.execute("DELETE FROM moto_imagens WHERE id = %s AND moto_id = %s", (imagem_id, moto_id))
            get_db().commit()

            flash("Imagem removida!", "info")
    except Exception as e:
        get_db().rollback()
        flash(f"Erro ao remover imagem: {e}", "error")

    return redirect(url_for('moto_imagens', moto_id=moto_id))

# === DOCUMENTO DA MOTO ===

@app.route("/motos/<int:moto_id>/documento", methods=["GET", "POST"])
def moto_documento(moto_id):
    with get_db().cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        # Confirma existência da moto
        cur.execute("SELECT * FROM motos WHERE id=%s", (moto_id,))
        moto = cur.fetchone()
        if not moto:
            flash("Moto não encontrada.", "error")
            return redirect(url_for("motos"))

        if request.method == "POST":
            file = request.files.get("documento")
            if not file or not allowed_documento(file.filename):
                flash("Arquivo inválido. Envie PDF, PNG ou JPG.", "error")
                return redirect(url_for("moto_documento", moto_id=moto_id))

            filename = secure_filename(file.filename)
            base, ext = os.path.splitext(filename)
            filename = f"moto_{moto_id}__documento{ext}"
            save_path = os.path.join(app.config["UPLOAD_FOLDER_DOCUMENTOS"], filename)

            # Remove documento antigo, se houver
            try:
                if moto["documento_arquivo"]:
                    old_path = os.path.join(app.config["UPLOAD_FOLDER_DOCUMENTOS"], moto["documento_arquivo"])
                    if os.path.exists(old_path):
                        os.remove(old_path)
            except Exception:
                pass

            try:
                file.save(save_path)
                cur.execute("UPDATE motos SET documento_arquivo=%s WHERE id=%s", (filename, moto_id))
                get_db().commit()
                flash("Documento da moto anexado com sucesso!", "success")
            except Exception as e:
                get_db().rollback()
                if os.path.exists(save_path):
                    try:
                        os.remove(save_path)
                    except Exception:
                        pass
                flash(f"Erro ao salvar documento: {e}", "error")

            return redirect(url_for("moto_documento", moto_id=moto_id))

        return render_template("moto_documento.html", moto=moto)

@app.route("/motos/<int:moto_id>/documento/excluir", methods=["POST"])
def excluir_documento_moto(moto_id):
    try:
        with get_db().cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT documento_arquivo FROM motos WHERE id=%s", (moto_id,))
            moto = cur.fetchone()
            if not moto:
                flash("Moto não encontrada.", "error")
                return redirect(url_for("motos"))

            if moto["documento_arquivo"]:
                filepath = os.path.join(app.config["UPLOAD_FOLDER_DOCUMENTOS"], moto["documento_arquivo"])
                if os.path.exists(filepath):
                    try:
                        os.remove(filepath)
                    except Exception:
                        pass

            cur.execute("UPDATE motos SET documento_arquivo=NULL WHERE id=%s", (moto_id,))
            get_db().commit()
            flash("Documento da moto removido com sucesso!", "info")
    except Exception as e:
        get_db().rollback()
        flash(f"Erro ao remover documento: {e}", "error")

    return redirect(url_for("moto_documento", moto_id=moto_id))

# === LOCAÇÕES (CRUD + Contrato + Asaas + Cancelamento) ===

@app.route("/locacoes", methods=["GET", "POST"])
def locacoes():
    if request.method == "POST":
        cliente_id = request.form["cliente_id"]
        moto_id = request.form["moto_id"]
        data_inicio = request.form["data_inicio"]
        observacoes = (request.form.get("observacoes") or "").strip()
        valor = float(request.form.get("valor") or 0)
        frequencia_pagamento = request.form.get("frequencia_pagamento")

        # Validação da frequência (precisa estar dentro do POST)
        if frequencia_pagamento not in FREQ_ALLOWED:
            flash("Frequência de pagamento inválida.", "error")
            return redirect(url_for("locacoes"))

        try:
            with get_db().cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                # Verificar se moto está disponível
                cur.execute("SELECT disponivel FROM motos WHERE id=%s", (moto_id,))
                moto = cur.fetchone()
                if not moto:
                    flash("Moto não encontrada.", "error")
                    return redirect(url_for("locacoes"))
                if not moto["disponivel"]:
                    flash("Moto já está alugada.", "error")
                    return redirect(url_for("locacoes"))

                # Upload do contrato PDF
                contrato_pdf = None
                contrato_path = None
                if "contrato_pdf" in request.files:
                    file = request.files["contrato_pdf"]
                    if file and allowed_contract(file.filename):
                        filename = secure_filename(file.filename)
                        base, ext = os.path.splitext(filename)
                        filename = f"contrato_loc_{cliente_id}_{moto_id}{ext}"
                        contrato_path = os.path.join(app.config["UPLOAD_FOLDER_CONTRATOS"], filename)
                        file.save(contrato_path)
                        contrato_pdf = filename

                # Buscar cliente para pegar o Asaas ID
                cur.execute("SELECT asaas_id FROM clientes WHERE id=%s", (cliente_id,))
                cliente = cur.fetchone()

                if not cliente or not cliente["asaas_id"]:
                    flash("Cliente não encontrado ou não integrado ao Asaas.", "error")
                    if contrato_pdf and contrato_path and os.path.exists(contrato_path):
                        os.remove(contrato_path)
                    return redirect(url_for("locacoes"))

                # Inicializar variáveis
                boleto_url = None
                asaas_payment_id = None
                asaas_subscription_id = None

                # Se for mensal ou semanal → cria assinatura
                if frequencia_pagamento in ["mensal", "semanal"]:
                    ciclo = "MONTHLY" if frequencia_pagamento == "mensal" else "WEEKLY"
                    subscription_data = {
                        "customer": cliente["asaas_id"],
                        "billingType": "BOLETO",
                        "value": valor,
                        "nextDueDate": data_inicio,
                        "cycle": ciclo,
                        "description": f"Locação da moto {moto_id}"
                    }

                    resp = requests.post(
                        f"{ASAAS_BASE_URL}/subscriptions",
                        headers=asaas_headers,
                        json=subscription_data
                    ).json()

                    if "errors" in resp:
                        msg = resp["errors"][0].get("description", "Erro ao criar assinatura.")
                        flash(f"Erro no Asaas: {msg}", "error")
                        if contrato_pdf and contrato_path and os.path.exists(contrato_path):
                            os.remove(contrato_path)
                        return redirect(url_for("locacoes"))

                    asaas_subscription_id = resp.get("id")

                else:
                    # Cobrança avulsa (única)
                    cobranca = criar_cobranca_asaas(cliente["asaas_id"], valor, data_inicio)
                    if "errors" in cobranca:
                        msg = cobranca["errors"][0].get("description", "Erro ao gerar boleto.")
                        flash(f"Erro no Asaas: {msg}", "error")
                        if contrato_pdf and contrato_path and os.path.exists(contrato_path):
                            os.remove(contrato_path)
                        return redirect(url_for("locacoes"))

                    boleto_url = cobranca.get("bankSlipUrl")
                    asaas_payment_id = cobranca.get("id")

                # Inserir locação com assinatura ou pagamento único
                cur.execute("""
                    INSERT INTO locacoes (cliente_id, moto_id, data_inicio, observacoes, valor,
                                          frequencia_pagamento, contrato_pdf, boleto_url,
                                          asaas_payment_id, asaas_subscription_id)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    RETURNING id
                """, (
                    cliente_id, moto_id, data_inicio, observacoes, valor,
                    frequencia_pagamento, contrato_pdf, boleto_url,
                    asaas_payment_id, asaas_subscription_id
                ))

                locacao_id = cur.fetchone()["id"]

                # Se foi pagamento único, inserir primeiro boleto na tabela boletos
                if asaas_payment_id and boleto_url:
                    cur.execute("""
                        INSERT INTO boletos (locacao_id, asaas_payment_id, status, valor, data_vencimento, boleto_url, descricao)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, (locacao_id, asaas_payment_id, "PENDING", valor, data_inicio, boleto_url, "Locação de Moto"))

                # Marcar moto como indisponível
                cur.execute("UPDATE motos SET disponivel=FALSE WHERE id=%s", (moto_id,))
                get_db().commit()

                if asaas_subscription_id:
                    flash("Locação com assinatura criada com sucesso! Os boletos serão gerados automaticamente.", "success")
                else:
                    flash("Locação criada com sucesso!", "success")

        except Exception as e:
            get_db().rollback()
            flash(f"Erro ao criar locação: {e}", "error")

        return redirect(url_for("locacoes"))

    # GET
    with get_db().cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("""
            SELECT l.id,
                c.nome AS cliente_nome,
                m.modelo AS moto_modelo,
                m.placa AS moto_placa,
                l.data_inicio,
                l.data_fim,
                l.cancelado,
                l.observacoes,
                l.contrato_pdf,
                l.boleto_url,
                l.pagamento_status,
                l.valor_pago,
                l.data_pagamento,
                l.frequencia_pagamento,
                l.asaas_subscription_id,
                COUNT(b.id) as total_boletos,
                COUNT(CASE WHEN b.status = 'RECEIVED' THEN 1 END) as boletos_pagos
            FROM locacoes l
            JOIN clientes c ON l.cliente_id = c.id
            JOIN motos m ON l.moto_id = m.id
            LEFT JOIN boletos b ON l.id = b.locacao_id
            WHERE l.cancelado = FALSE
            GROUP BY l.id, c.nome, m.modelo, m.placa
            ORDER BY l.data_inicio DESC
        """)
        locacoes = cur.fetchall()

        cur.execute("SELECT id, nome FROM clientes")
        clientes = cur.fetchall()

        cur.execute("SELECT id, modelo, placa FROM motos WHERE disponivel=TRUE")
        motos = cur.fetchall()

        return render_template("locacoes.html", locacoes=locacoes, clientes=clientes, motos=motos)

@app.route("/locacoes/<int:id>/editar", methods=["GET", "POST"])
def editar_locacao(id):
    with get_db().cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        if request.method == "POST":
            data_inicio = request.form["data_inicio"]
            data_fim = request.form.get("data_fim") or None
            observacoes = (request.form.get("observacoes") or "").strip()

            contrato_pdf = None
            contrato_path = None

            if "contrato_pdf" in request.files:
                file = request.files["contrato_pdf"]
                if file and allowed_contract(file.filename):
                    filename = secure_filename(file.filename)
                    base, ext = os.path.splitext(filename)
                    filename = f"contrato_loc_{id}_edit{ext}"
                    contrato_path = os.path.join(app.config["UPLOAD_FOLDER_CONTRATOS"], filename)
                    file.save(contrato_path)
                    contrato_pdf = filename

            try:
                # Se novo contrato foi enviado, remove o antigo
                if contrato_pdf:
                    cur.execute("SELECT contrato_pdf FROM locacoes WHERE id=%s", (id,))
                    antigo = cur.fetchone()
                    if antigo and antigo["contrato_pdf"]:
                        old_path = os.path.join(app.config["UPLOAD_FOLDER_CONTRATOS"], antigo["contrato_pdf"])
                        if os.path.exists(old_path):
                            try:
                                os.remove(old_path)
                            except Exception:
                                pass

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

                get_db().commit()
                flash("Locação atualizada com sucesso!", "success")
            except Exception as e:
                get_db().rollback()
                # Remove novo contrato se erro
                if contrato_pdf and contrato_path and os.path.exists(contrato_path):
                    try:
                        os.remove(contrato_path)
                    except Exception:
                        pass
                flash(f"Erro ao atualizar locação: {e}", "error")

            return redirect(url_for("locacoes"))

        # GET - Sincronizar boletos antes de exibir
        sincronizar_boletos_locacao(id)

        cur.execute("""
            SELECT l.*, c.nome as cliente_nome, m.modelo as moto_modelo, m.placa as moto_placa
            FROM locacoes l
            JOIN clientes c ON l.cliente_id = c.id
            JOIN motos m ON l.moto_id = m.id
            WHERE l.id=%s
        """, (id,))
        locacao = cur.fetchone()
        if not locacao:
            flash("Locação não encontrada.", "error")
            return redirect(url_for("locacoes"))

        # Buscar boletos da locação
        cur.execute("""
            SELECT * FROM boletos
            WHERE locacao_id = %s
            ORDER BY data_vencimento DESC, created_at DESC
        """, (id,))
        boletos = cur.fetchall()

        return render_template("editar_locacao.html", locacao=locacao, boletos=boletos)

@app.route("/locacoes/<int:id>/cancelar", methods=["POST"])
def cancelar_locacao(id):
    """
    Cancela a locação:
    - Libera a moto
    - Marca a locação como cancelada e define data_fim = hoje
    - Se houver asaas_subscription_id → cancela assinatura no Asaas
    - Se houver asaas_payment_id pendente → tenta cancelar pagamento no Asaas
    """
    try:
        with get_db().cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            # Buscar dados necessários
            cur.execute("""
                SELECT l.id, l.moto_id, l.cancelado, l.asaas_subscription_id, l.asaas_payment_id, l.pagamento_status
                FROM locacoes l
                WHERE l.id = %s
                LIMIT 1
            """, (id,))
            loc = cur.fetchone()

            if not loc:
                flash("Locação não encontrada.", "error")
                return redirect(url_for("locacoes"))

            if loc["cancelado"]:
                flash("Esta locação já está cancelada.", "info")
                return redirect(url_for("locacoes"))

            mensagens = []

            # 1) Cancelar assinatura (para locações recorrentes)
            if loc.get("asaas_subscription_id"):
                ok, msg = cancelar_assinatura_asaas(loc["asaas_subscription_id"])
                mensagens.append(msg)

            # 2) Cancelar pagamento único pendente (para locações avulsas)
            if loc.get("asaas_payment_id") and (loc.get("pagamento_status") in (None, "", "PENDING")):
                ok, msg = cancelar_pagamento_asaas(loc["asaas_payment_id"])
                mensagens.append(msg)
                # Opcional: atualizar status local como CANCELLED
                if ok:
                    cur.execute("""
                        UPDATE locacoes
                        SET pagamento_status = 'CANCELLED'
                        WHERE id = %s
                    """, (id,))

            # 3) Cancelar locação local + liberar moto
            hoje = datetime.now().date().isoformat()
            cur.execute("UPDATE locacoes SET cancelado = TRUE, data_fim = %s WHERE id = %s", (hoje, id))
            cur.execute("UPDATE motos SET disponivel = TRUE WHERE id = %s", (loc["moto_id"],))

            get_db().commit()

            # Feedback amigável
            base_msg = "Locação cancelada com sucesso!"
            if mensagens:
                base_msg += " " + " ".join(mensagens)
            flash(base_msg, "info")

    except Exception as e:
        get_db().rollback()
        flash(f"Erro ao cancelar locação: {e}", "error")

    return redirect(url_for("locacoes"))

# === LOCAÇÕES CANCELADAS ===

@app.route("/locacoes/canceladas")
def locacoes_canceladas():
    with get_db().cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("""
            SELECT l.id,
                c.nome AS cliente_nome,
                m.modelo AS moto_modelo,
                m.placa AS moto_placa,
                l.data_inicio,
                l.data_fim,
                l.observacoes,
                l.contrato_pdf,
                l.boleto_url,
                l.pagamento_status,
                l.valor_pago,
                l.data_pagamento,
                l.frequencia_pagamento,
                l.valor,
                l.asaas_subscription_id,
                l.asaas_payment_id,
                -- Estatísticas dos boletos
                COUNT(b.id) as total_boletos,
                COUNT(CASE WHEN b.status = 'RECEIVED' THEN 1 END) as boletos_pagos,
                COUNT(CASE WHEN b.status = 'PENDING' THEN 1 END) as boletos_pendentes,
                COUNT(CASE WHEN b.status = 'OVERDUE' THEN 1 END) as boletos_vencidos,
                COUNT(CASE WHEN b.status = 'CANCELLED' THEN 1 END) as boletos_cancelados,
                -- Último boleto gerado
                MAX(b.data_vencimento) as ultimo_vencimento,
                -- Status do último boleto
                (SELECT b2.status
                 FROM boletos b2
                 WHERE b2.locacao_id = l.id
                 ORDER BY b2.data_vencimento DESC, b2.id DESC
                 LIMIT 1) as status_ultimo_boleto,
                -- URL do último boleto
                (SELECT b2.boleto_url
                 FROM boletos b2
                 WHERE b2.locacao_id = l.id
                 ORDER BY b2.data_vencimento DESC, b2.id DESC
                 LIMIT 1) as url_ultimo_boleto,
                -- Total pago via boletos
                COALESCE(SUM(CASE WHEN b.status = 'RECEIVED' THEN b.valor_pago END), 0) as total_recebido_boletos
            FROM locacoes l
            JOIN clientes c ON l.cliente_id = c.id
            JOIN motos m ON l.moto_id = m.id
            LEFT JOIN boletos b ON l.id = b.locacao_id
            WHERE l.cancelado = TRUE
            GROUP BY l.id, c.nome, m.modelo, m.placa
            ORDER BY l.data_fim DESC, l.data_inicio DESC
        """)
        canceladas = cur.fetchall()

        return render_template("locacoes_canceladas.html", canceladas=canceladas)

# === SERVIÇOS NAS LOCAÇÕES ===

@app.route("/locacoes/<int:locacao_id>/servicos", methods=["GET", "POST"])
def servicos_locacao(locacao_id):
    # Verifica a locação antes de qualquer operação
    with get_db().cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("""
            SELECT l.id, c.nome AS cliente_nome, m.modelo AS moto_modelo, m.placa AS moto_placa
            FROM locacoes l
            JOIN clientes c ON l.cliente_id = c.id
            JOIN motos m ON l.moto_id = m.id
            WHERE l.id = %s
        """, (locacao_id,))
        locacao = cur.fetchone()
        if not locacao:
            flash("Locação não encontrada.", "error")
            return redirect(url_for("locacoes"))

        if request.method == "POST":
            descricao = (request.form.get("descricao") or "").strip()
            valor = request.form.get("valor") or 0
            quilometragem = request.form.get("quilometragem") or None

            if not descricao:
                flash("Descrição do serviço é obrigatória.", "error")
                return redirect(url_for("servicos_locacao", locacao_id=locacao_id))

            try:
                cur.execute("""
                    INSERT INTO servicos_locacao (locacao_id, descricao, valor, quilometragem)
                    VALUES (%s, %s, %s, %s)
                """, (locacao_id, descricao, valor, quilometragem))
                get_db().commit()
                flash("Serviço adicionado com sucesso!", "success")
            except Exception as e:
                get_db().rollback()
                flash(f"Erro ao adicionar serviço: {e}", "error")

            return redirect(url_for("servicos_locacao", locacao_id=locacao_id))

        # GET: listar serviços
        cur.execute("""
            SELECT id, descricao, valor, data_servico, quilometragem
            FROM servicos_locacao
            WHERE locacao_id = %s
            ORDER BY data_servico DESC, id DESC
        """, (locacao_id,))
        servicos = cur.fetchall()

        return render_template("servicos_locacao.html", locacao=locacao, servicos=servicos)

@app.route("/locacoes/<int:locacao_id>/servicos/<int:servico_id>/excluir", methods=["POST"])
def excluir_servico_locacao(locacao_id, servico_id):
    try:
        with get_db().cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            # Confirma que o serviço pertence àquela locação
            cur.execute("""
                SELECT id FROM servicos_locacao
                WHERE id = %s AND locacao_id = %s
            """, (servico_id, locacao_id))
            reg = cur.fetchone()
            if not reg:
                flash("Serviço não encontrado para esta locação.", "error")
                return redirect(url_for("servicos_locacao", locacao_id=locacao_id))

            cur.execute("DELETE FROM servicos_locacao WHERE id=%s AND locacao_id=%s", (servico_id, locacao_id))
            get_db().commit()

            flash("Serviço removido com sucesso!", "info")
    except Exception as e:
        get_db().rollback()
        flash(f"Erro ao remover serviço: {e}", "error")

    return redirect(url_for("servicos_locacao", locacao_id=locacao_id))

# === BOLETOS DA LOCAÇÃO ===

@app.route("/locacoes/<int:locacao_id>/boletos")
def boletos_locacao(locacao_id):
    with get_db().cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        # Dados da locação (cliente/moto) para cabeçalho
        cur.execute("""
            SELECT l.id, l.data_inicio, l.data_fim, l.frequencia_pagamento, l.valor,
                   l.asaas_subscription_id, l.asaas_payment_id, l.pagamento_status,
                   c.nome AS cliente_nome, m.modelo AS moto_modelo, m.placa AS moto_placa
            FROM locacoes l
            JOIN clientes c ON l.cliente_id = c.id
            JOIN motos m ON l.moto_id = m.id
            WHERE l.id = %s
        """, (locacao_id,))
        locacao = cur.fetchone()
        if not locacao:
            flash("Locação não encontrada.", "error")
            return redirect(url_for("locacoes"))

        # Lista de boletos vinculados a essa locação
        cur.execute("""
            SELECT b.id, b.asaas_payment_id, b.status, b.valor, b.valor_pago,
                   b.data_vencimento, b.data_pagamento, b.boleto_url, b.descricao,
                   b.created_at
            FROM boletos b
            WHERE b.locacao_id = %s
            ORDER BY b.data_vencimento DESC NULLS LAST, b.id DESC
        """, (locacao_id,))
        boletos = cur.fetchall()

        # Estatísticas rápidas
        cur.execute("""
            SELECT
                COUNT(*)::int AS total,
                COUNT(CASE WHEN status = 'RECEIVED' THEN 1 END)::int AS pagos,
                COUNT(CASE WHEN status = 'PENDING' THEN 1 END)::int AS pendentes,
                COUNT(CASE WHEN status = 'OVERDUE' THEN 1 END)::int AS vencidos,
                COUNT(CASE WHEN status = 'CANCELLED' THEN 1 END)::int AS cancelados,
                COALESCE(SUM(CASE WHEN status = 'RECEIVED' THEN COALESCE(valor_pago, valor) END), 0) AS total_recebido
            FROM boletos
            WHERE locacao_id = %s
        """, (locacao_id,))
        stats = cur.fetchone()

    return render_template("boletos_locacao.html", locacao=locacao, boletos=boletos, stats=stats)

# === WEBHOOK ASAAS ===

@app.route("/webhook/asaas", methods=["POST"])
def webhook_asaas():
    """
    Webhook para receber notificações do Asaas sobre mudanças de status de pagamentos
    """
    try:
        # Verificar assinatura do webhook (segurança)
        webhook_secret = app.config.get("ASAAS_WEBHOOK_SECRET")
        if webhook_secret:
            signature = request.headers.get("X-Asaas-Signature")
            if not signature:
                return jsonify({"error": "Missing signature"}), 401
            
            payload = request.get_data()
            expected_signature = hmac.new(
                webhook_secret.encode(),
                payload,
                hashlib.sha256
            ).hexdigest()
            
            if not hmac.compare_digest(signature, expected_signature):
                return jsonify({"error": "Invalid signature"}), 401

        data = request.get_json()
        if not data:
            return jsonify({"error": "No data"}), 400

        event = data.get("event")
        payment_data = data.get("payment", {})
        payment_id = payment_data.get("id")

        if not payment_id:
            return jsonify({"error": "No payment ID"}), 400

        # Atualizar status do boleto na tabela boletos
        with get_db().cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                UPDATE boletos SET
                    status = %s,
                    valor_pago = %s,
                    data_pagamento = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE asaas_payment_id = %s
            """, (
                payment_data.get("status"),
                payment_data.get("paidValue"),
                payment_data.get("paymentDate"),
                payment_id
            ))

            # Se o pagamento foi confirmado, atualizar também a tabela locacoes
            if payment_data.get("status") == "RECEIVED":
                cur.execute("""
                    UPDATE locacoes SET
                        pagamento_status = 'RECEIVED',
                        valor_pago = %s,
                        data_pagamento = %s
                    WHERE asaas_payment_id = %s
                """, (
                    payment_data.get("paidValue"),
                    payment_data.get("paymentDate"),
                    payment_id
                ))

            get_db().commit()

        return jsonify({"status": "success"}), 200

    except Exception as e:
        print(f"Erro no webhook: {e}")
        return jsonify({"error": "Internal error"}), 500

# === ROTAS DE ARQUIVOS ===

@app.route("/uploads/motos/<filename>")
def uploaded_moto_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER_MOTOS"], filename)

@app.route("/uploads/contratos/<filename>")
def uploaded_contrato_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER_CONTRATOS"], filename)

@app.route("/uploads/habilitacoes/<filename>")
def uploaded_habilitacao_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER_HABILITACOES"], filename)

@app.route("/uploads/documentos/<filename>")
def uploaded_documento_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER_DOCUMENTOS"], filename)

# === SINCRONIZAÇÃO MANUAL ===

@app.route("/locacoes/<int:locacao_id>/sincronizar", methods=["POST"])
def sincronizar_locacao_manual(locacao_id):
    """Rota para sincronizar manualmente os boletos de uma locação"""
    try:
        sucesso = sincronizar_boletos_locacao(locacao_id)
        if sucesso:
            flash("Boletos sincronizados com sucesso!", "success")
        else:
            flash("Erro ao sincronizar boletos. Verifique se o cliente está integrado ao Asaas.", "error")
    except Exception as e:
        flash(f"Erro ao sincronizar: {e}", "error")
    
    return redirect(url_for("editar_locacao", id=locacao_id))

# === INICIALIZAÇÃO ===

if __name__ == "__main__":
    app.run(debug=True)