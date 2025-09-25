import os
from flask import Blueprint, render_template, request, redirect, url_for, flash, send_from_directory, current_app
from flask_login import login_required
from database import get_db_connection
from werkzeug.utils import secure_filename

clientes_bp = Blueprint("clientes", __name__, url_prefix="/clientes")

# ======================
# Listar e cadastrar cliente
# ======================
@clientes_bp.route("/", methods=["GET", "POST"])
@login_required
def listar_clientes():
    conn = get_db_connection()
    cur = conn.cursor()

    if request.method == "POST":
        nome = request.form["nome"]
        email = request.form["email"]
        telefone = request.form["telefone"]
        cpf = request.form.get("cpf")
        endereco = request.form.get("endereco")
        data_nascimento = request.form.get("data_nascimento") or None
        observacoes = request.form.get("observacoes")

        cur.execute("""
            INSERT INTO clientes (nome, email, telefone, cpf, endereco, data_nascimento, observacoes)
            VALUES (%s,%s,%s,%s,%s,%s,%s)
        """, (nome, email, telefone, cpf, endereco, data_nascimento, observacoes))
        conn.commit()
        flash("Cliente cadastrado com sucesso!", "success")
        return redirect(url_for("clientes.listar_clientes"))

    cur.execute("SELECT * FROM clientes ORDER BY nome")
    clientes = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("clientes.html", clientes=clientes)

# ======================
# Editar cliente
# ======================
@clientes_bp.route("/<int:id>/editar", methods=["GET", "POST"])
@login_required
def editar_cliente(id):
    conn = get_db_connection()
    cur = conn.cursor()

    if request.method == "POST":
        nome = request.form["nome"]
        email = request.form["email"]
        telefone = request.form["telefone"]
        cpf = request.form.get("cpf")
        endereco = request.form.get("endereco")
        data_nascimento = request.form.get("data_nascimento") or None
        observacoes = request.form.get("observacoes")

        cur.execute("""
            UPDATE clientes SET nome=%s, email=%s, telefone=%s, cpf=%s,
            endereco=%s, data_nascimento=%s, observacoes=%s
            WHERE id=%s
        """, (nome, email, telefone, cpf, endereco, data_nascimento, observacoes, id))
        conn.commit()
        flash("Cliente atualizado com sucesso!", "success")
        return redirect(url_for("clientes.listar_clientes"))

    cur.execute("SELECT * FROM clientes WHERE id=%s", (id,))
    cliente = cur.fetchone()
    cur.close()
    conn.close()
    return render_template("editar_cliente.html", cliente=cliente)

# ======================
# Excluir cliente
# ======================
@clientes_bp.route("/<int:id>/deletar", methods=["POST"])
@login_required
def deletar_cliente(id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM clientes WHERE id=%s", (id,))
    conn.commit()
    cur.close()
    conn.close()
    flash("Cliente removido!", "info")
    return redirect(url_for("clientes.listar_clientes"))

# ======================
# Upload da habilitação (CNH)
# ======================
@clientes_bp.route("/<int:id>/habilitacao", methods=["GET", "POST"])
@login_required
def cliente_habilitacao(id):
    conn = get_db_connection()
    cur = conn.cursor()

    if request.method == "POST":
        if "arquivo" not in request.files:
            flash("Nenhum arquivo enviado.", "danger")
            return redirect(request.url)

        file = request.files["arquivo"]
        if file.filename == "":
            flash("Nenhum arquivo selecionado.", "danger")
            return redirect(request.url)

        if file:
            filename = secure_filename(file.filename)
            pasta = os.path.join(current_app.config["UPLOAD_FOLDER"], "habilitacoes")
            os.makedirs(pasta, exist_ok=True)
            filepath = os.path.join(pasta, filename)
            file.save(filepath)

            # atualizar no banco
            cur.execute("UPDATE clientes SET habilitacao_arquivo=%s WHERE id=%s", (filename, id))
            conn.commit()
            flash("Habilitação enviada com sucesso!", "success")
            return redirect(url_for("clientes.cliente_habilitacao", id=id))

    cur.execute("SELECT habilitacao_arquivo FROM clientes WHERE id=%s", (id,))
    cliente = cur.fetchone()
    cur.close()
    conn.close()
    return render_template("cliente_habilitacao.html", cliente=cliente, id=id)

# ======================
# Download da CNH
# ======================
@clientes_bp.route("/habilitacoes/<filename>")
@login_required
def uploaded_habilitacao(filename):
    pasta = os.path.join(current_app.config["UPLOAD_FOLDER"], "habilitacoes")
    return send_from_directory(pasta, filename)