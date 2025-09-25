import os
import time
import psycopg2
from flask import Blueprint, render_template, request, redirect, url_for, flash, send_from_directory, current_app
from flask_login import login_required
from werkzeug.utils import secure_filename
from database import get_db_connection

motos_bp = Blueprint("motos", __name__, url_prefix="/motos")

# ======================
# Helpers
# ======================
ALLOWED_DOC_EXT = {"pdf", "png", "jpg", "jpeg"}
ALLOWED_IMG_EXT = {"png", "jpg", "jpeg"}

def _allowed(filename, allowed):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in allowed

def _unique_filename(prefix_id, filename):
    name, ext = os.path.splitext(filename)
    ts = int(time.time() * 1000)
    return f"{prefix_id}_{ts}{ext.lower()}"

# ======================
# Listar e cadastrar motos
# ======================
@motos_bp.route("/", methods=["GET", "POST"])
@login_required
def listar_motos():
    conn = get_db_connection()
    cur = conn.cursor()

    if request.method == "POST":
        placa = request.form["placa"].strip().upper()
        modelo = request.form["modelo"].strip()
        ano = request.form.get("ano") or None
        disponivel = True

        try:
            cur.execute("""
                INSERT INTO motos (placa, modelo, ano, disponivel)
                VALUES (%s, %s, %s, %s)
            """, (placa, modelo, ano, disponivel))
            conn.commit()
            flash("Moto cadastrada com sucesso!", "success")
        except Exception as e:
            conn.rollback()
            flash(f"Erro ao cadastrar moto: {e}", "danger")
        finally:
            cur.close()
            conn.close()

        return redirect(url_for("motos.listar_motos"))

    cur.execute("SELECT id, placa, modelo, ano, disponivel, documento_arquivo, imagem FROM motos ORDER BY modelo")
    motos = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("motos.html", motos=motos)

# ======================
# Editar moto
# ======================
@motos_bp.route("/<int:id>/editar", methods=["GET", "POST"])
@login_required
def editar_moto(id):
    conn = get_db_connection()
    cur = conn.cursor()

    if request.method == "POST":
        placa = request.form["placa"].strip().upper()
        modelo = request.form["modelo"].strip()
        ano = request.form.get("ano") or None
        disponivel = bool(request.form.get("disponivel"))

        try:
            cur.execute("""
                UPDATE motos SET placa=%s, modelo=%s, ano=%s, disponivel=%s
                WHERE id=%s
            """, (placa, modelo, ano, disponivel, id))
            conn.commit()
            flash("Moto atualizada com sucesso!", "success")
            return redirect(url_for("motos.listar_motos"))
        except Exception as e:
            conn.rollback()
            flash(f"Erro ao atualizar moto: {e}", "danger")

    cur.execute("SELECT id, placa, modelo, ano, disponivel, documento_arquivo, imagem FROM motos WHERE id=%s", (id,))
    moto = cur.fetchone()
    cur.close()
    conn.close()
    return render_template("editar_moto.html", moto=moto)

# ======================
# Excluir moto
# ======================
@motos_bp.route("/<int:id>/excluir", methods=["POST"])
@login_required
def excluir_moto(id):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM motos WHERE id=%s", (id,))
        conn.commit()
        flash("Moto excluída com sucesso!", "info")
    except psycopg2.errors.ForeignKeyViolation as e:
        conn.rollback()
        detalhe = getattr(e.diag, "message_detail", "")
        if detalhe:
            flash(f"Erro ao excluir moto: {detalhe}", "danger")
        else:
            flash("Não é possível excluir: a moto está vinculada a uma locação.", "danger")
    except Exception as e:
        conn.rollback()
        flash(f"Erro inesperado ao excluir moto: {e}", "danger")
    finally:
        cur.close()
        conn.close()
    return redirect(url_for("motos.listar_motos"))

# ======================
# Documento da moto (upload/visualização)
# ======================
@motos_bp.route("/<int:moto_id>/documento", methods=["GET", "POST"])
@login_required
def moto_documento(moto_id):
    conn = get_db_connection()
    cur = conn.cursor()

    if request.method == "POST":
        if "documento" not in request.files:
            flash("Nenhum arquivo enviado.", "danger")
            return redirect(request.url)

        file = request.files["documento"]
        if file.filename == "":
            flash("Nenhum arquivo selecionado.", "danger")
            return redirect(request.url)

        if not _allowed(file.filename, ALLOWED_DOC_EXT):
            flash("Formato inválido. Envie PDF, PNG, JPG ou JPEG.", "warning")
            return redirect(request.url)

        try:
            filename = secure_filename(file.filename)
            filename = _unique_filename(moto_id, filename)
            pasta = os.path.join(current_app.config["UPLOAD_FOLDER"], "contratos")  
            os.makedirs(pasta, exist_ok=True)
            file.save(os.path.join(pasta, filename))

            cur.execute("UPDATE motos SET documento_arquivo=%s WHERE id=%s", (filename, moto_id))
            conn.commit()
            flash("Documento enviado com sucesso!", "success")
            return redirect(url_for("motos.moto_documento", moto_id=moto_id))
        except Exception as e:
            conn.rollback()
            flash(f"Erro ao enviar documento: {e}", "danger")

    cur.execute("SELECT id, placa, modelo, documento_arquivo FROM motos WHERE id=%s", (moto_id,))
    moto = cur.fetchone()
    cur.close()
    conn.close()
    return render_template("moto_documento.html", moto=moto)

@motos_bp.route("/<int:moto_id>/documento/excluir", methods=["POST"])
@login_required
def excluir_documento_moto(moto_id):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT documento_arquivo FROM motos WHERE id=%s", (moto_id,))
        row = cur.fetchone()
        if row and row[0]:
            filename = row[0]
            pasta = os.path.join(current_app.config["UPLOAD_FOLDER"], "contratos")
            filepath = os.path.join(pasta, filename)
            if os.path.exists(filepath):
                try:
                    os.remove(filepath)
                except Exception:
                    pass

        cur.execute("UPDATE motos SET documento_arquivo=NULL WHERE id=%s", (moto_id,))
        conn.commit()
        flash("Documento da moto removido com sucesso!", "info")
    except Exception as e:
        conn.rollback()
        flash(f"Erro ao remover documento: {e}", "danger")
    finally:
        cur.close()
        conn.close()
    return redirect(url_for("motos.moto_documento", moto_id=moto_id))

@motos_bp.route("/documentos/<filename>")
@login_required
def serve_documento_moto(filename):
    pasta = os.path.join(current_app.config["UPLOAD_FOLDER"], "contratos")
    return send_from_directory(pasta, filename)

# ======================
# Imagens da moto (upload múltiplo/lista/excluir)
# ======================
@motos_bp.route("/<int:moto_id>/imagens", methods=["GET", "POST"])
@login_required
def moto_imagens(moto_id):
    conn = get_db_connection()
    cur = conn.cursor()

    if request.method == "POST":
        files = request.files.getlist("imagens")
        if not files or files == [None]:
            flash("Nenhuma imagem selecionada.", "warning")
            return redirect(request.url)

        pasta = os.path.join(current_app.config["UPLOAD_FOLDER"], "motos")
        os.makedirs(pasta, exist_ok=True)

        count_ok = 0
        try:
            for f in files:
                if not f or f.filename == "":
                    continue
                if not _allowed(f.filename, ALLOWED_IMG_EXT):
                    continue
                filename = secure_filename(f.filename)
                filename = _unique_filename(moto_id, filename)
                f.save(os.path.join(pasta, filename))

                cur.execute("""
                    INSERT INTO moto_imagens (moto_id, arquivo)
                    VALUES (%s, %s)
                """, (moto_id, filename))
                count_ok += 1

            conn.commit()
            if count_ok > 0:
                flash(f"{count_ok} imagem(ns) enviada(s) com sucesso!", "success")
            else:
                flash("Nenhuma imagem válida foi enviada.", "warning")
            return redirect(url_for("motos.moto_imagens", moto_id=moto_id))
        except Exception as e:
            conn.rollback()
            flash(f"Erro ao enviar imagens: {e}", "danger")

    cur.execute("SELECT id, placa, modelo FROM motos WHERE id=%s", (moto_id,))
    moto = cur.fetchone()

    cur.execute("SELECT id, arquivo, data_upload FROM moto_imagens WHERE moto_id=%s ORDER BY id DESC", (moto_id,))
    imagens = cur.fetchall()

    cur.close()
    conn.close()
    return render_template("moto_imagens.html", moto=moto, imagens=imagens, moto_id=moto_id)

@motos_bp.route("/<int:moto_id>/imagens/<int:img_id>/excluir", methods=["POST"])
@login_required
def excluir_imagem_moto(moto_id, img_id):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT arquivo FROM moto_imagens WHERE id=%s AND moto_id=%s", (img_id, moto_id))
        row = cur.fetchone()
        if row:
            filename = row[0]
            pasta = os.path.join(current_app.config["UPLOAD_FOLDER"], "motos")
            filepath = os.path.join(pasta, filename)
            if os.path.exists(filepath):
                try:
                    os.remove(filepath)
                except Exception:
                    pass

            cur.execute("DELETE FROM moto_imagens WHERE id=%s", (img_id,))
            conn.commit()
            flash("Imagem removida!", "info")
        else:
            flash("Imagem não encontrada.", "warning")
    except Exception as e:
        conn.rollback()
        flash(f"Erro ao remover imagem: {e}", "danger")
    finally:
        cur.close()
        conn.close()

    return redirect(url_for("motos.moto_imagens", moto_id=moto_id))

@motos_bp.route("/imagens/<filename>")
@login_required
def serve_imagem_moto(filename):
    pasta = os.path.join(current_app.config["UPLOAD_FOLDER"], "motos")
    return send_from_directory(pasta, filename)