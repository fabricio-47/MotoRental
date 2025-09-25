import datetime as dt
import requests
import psycopg2
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from database import get_db_connection
from config import Config

locacoes_bp = Blueprint("locacoes", __name__, url_prefix="/locacoes")

# ==== Listar locações ativas + Criar nova ====
@locacoes_bp.route("/", methods=["GET", "POST"])
@login_required
def listar_locacoes():
    conn = get_db_connection()
    cur = conn.cursor()

    if request.method == "POST":
        try:
            # 1) Ler e validar inputs do form
            cliente_id = request.form.get("cliente_id", type=int)
            moto_id = request.form.get("moto_id", type=int)
            data_inicio_str = (request.form.get("data_inicio") or "").strip()
            data_fim_str = (request.form.get("data_fim") or "").strip() or None
            valor_str = (request.form.get("valor") or "").strip()
            observacoes = (request.form.get("observacoes") or "").strip() or None

            # Frequência (aceita WEEKLY/MONTHLY direto ou SEMANAL/MENSAL e converte)
            freq = (request.form.get("frequencia_pagamento") or "").strip().upper()
            mapping = {"SEMANAL": "WEEKLY", "MENSAL": "MONTHLY"}
            frequencia = mapping.get(freq, freq)

            # Validações básicas
            if frequencia not in ("WEEKLY", "MONTHLY"):
                flash("Frequência inválida. Selecione semanal ou mensal.", "warning")
                return redirect(url_for("locacoes.listar_locacoes"))

            if not cliente_id or not moto_id:
                flash("Cliente e moto são obrigatórios.", "warning")
                return redirect(url_for("locacoes.listar_locacoes"))

            if not data_inicio_str:
                flash("Data de início é obrigatória.", "warning")
                return redirect(url_for("locacoes.listar_locacoes"))

            if not valor_str:
                flash("Valor é obrigatório.", "warning")
                return redirect(url_for("locacoes.listar_locacoes"))

            # 2) Parse de datas e valor
            # Se data vem como dd/mm/aaaa, converte para YYYY-MM-DD
            def parse_date_flexible(s):
                if "/" in s:  # dd/mm/aaaa
                    return dt.datetime.strptime(s, "%d/%m/%Y").strftime("%Y-%m-%d")
                else:  # já em YYYY-MM-DD
                    return s

            data_inicio = parse_date_flexible(data_inicio_str)
            data_fim = parse_date_flexible(data_fim_str) if data_fim_str else None

            # Converter valor (pt-BR -> float)
            valor = float(valor_str.replace(".", "").replace(",", "."))

            # 3) Buscar dados do cliente/moto
            cur.execute("SELECT asaas_id, nome FROM clientes WHERE id=%s", (cliente_id,))
            cliente = cur.fetchone()
            if not cliente:
                flash("Cliente não encontrado.", "danger")
                return redirect(url_for("locacoes.listar_locacoes"))
            if not cliente[0]:
                flash("Cliente sem integração Asaas (asaas_id ausente).", "danger")
                return redirect(url_for("locacoes.listar_locacoes"))

            cur.execute("SELECT modelo, placa, disponivel FROM motos WHERE id=%s", (moto_id,))
            moto = cur.fetchone()
            if not moto:
                flash("Moto não encontrada.", "danger")
                return redirect(url_for("locacoes.listar_locacoes"))
            if not moto[2]:  # disponivel
                flash("Moto indisponível para locação.", "warning")
                return redirect(url_for("locacoes.listar_locacoes"))

            # 4) Criar assinatura no Asaas
            subscription_data = {
                "customer": cliente[0],
                "billingType": "BOLETO",
                "value": valor,
                "cycle": frequencia,
                "description": f"Locação moto {moto[0]} - {moto[1]} ({cliente[1]})",
                "nextDueDate": data_inicio
            }
            if data_fim:
                subscription_data["endDate"] = data_fim

            resp = requests.post(
                f"{Config.ASAAS_BASE_URL}/subscriptions",
                headers={"access_token": Config.ASAAS_API_KEY},
                json=subscription_data,
                timeout=30
            )
            if resp.status_code not in (200, 201):
                flash(f"Erro ao criar assinatura no Asaas: {resp.text}", "danger")
                return redirect(url_for("locacoes.listar_locacoes"))

            asaas_subscription_id = resp.json().get("id")

            # 5) Salvar locação no banco
            cur.execute("""
                INSERT INTO locacoes (
                    cliente_id, moto_id, data_inicio, data_fim,
                    valor, frequencia_pagamento, observacoes, asaas_subscription_id
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
            """, (cliente_id, moto_id, data_inicio, data_fim,
                  valor, frequencia, observacoes, asaas_subscription_id))

            # 6) Marcar moto como indisponível
            cur.execute("UPDATE motos SET disponivel=FALSE WHERE id=%s", (moto_id,))
            conn.commit()
            flash("Locação criada e assinatura recorrente configurada no Asaas!", "success")
            return redirect(url_for("locacoes.listar_locacoes"))

        except psycopg2.Error as e:
            conn.rollback()
            detalhe = getattr(e.diag, "message_detail", "")
            if detalhe:
                flash(f"Erro ao criar locação: {detalhe}", "danger")
            else:
                flash(f"Erro ao criar locação: {e.pgerror or str(e)}", "danger")
        except ValueError as e:
            conn.rollback()
            flash(f"Data/valor inválido: {str(e)}", "danger")
        except Exception as e:
            conn.rollback()
            flash(f"Erro inesperado ao criar locação: {str(e)}", "danger")
        finally:
            cur.close()
            conn.close()
        return redirect(url_for("locacoes.listar_locacoes"))

    # GET
    cur.execute("""
        SELECT l.id, l.data_inicio, l.data_fim, l.valor, l.frequencia_pagamento,
               l.pagamento_status, l.valor_pago, l.asaas_subscription_id, l.boleto_url,
               c.nome AS cliente_nome, m.modelo AS moto_modelo, m.placa AS moto_placa
        FROM locacoes l
        JOIN clientes c ON l.cliente_id = c.id
        JOIN motos m ON l.moto_id = m.id
        WHERE l.cancelado = FALSE
        ORDER BY l.data_inicio DESC
    """)
    locacoes = cur.fetchall()

    cur.execute("SELECT id, nome FROM clientes ORDER BY nome")
    clientes = cur.fetchall()

    cur.execute("SELECT id, modelo, placa FROM motos WHERE disponivel = TRUE ORDER BY modelo")
    motos = cur.fetchall()

    cur.close()
    conn.close()
    return render_template("locacoes.html", locacoes=locacoes, clientes=clientes, motos=motos)

# ==== Editar locação + listar boletos ====
@locacoes_bp.route("/<int:id>/editar", methods=["GET", "POST"])
@login_required
def editar_locacao(id):
    conn = get_db_connection()
    cur = conn.cursor()

    if request.method == "POST":
        data_inicio = request.form["data_inicio"]
        data_fim = request.form.get("data_fim") or None
        valor = request.form["valor"]
        frequencia = request.form["frequencia_pagamento"]
        observacoes = request.form.get("observacoes")

        try:
            cur.execute("""
                UPDATE locacoes SET data_inicio=%s, data_fim=%s, valor=%s,
                       frequencia_pagamento=%s, observacoes=%s WHERE id=%s
            """, (data_inicio, data_fim, valor, frequencia, observacoes, id))

            cur.execute("SELECT asaas_subscription_id FROM locacoes WHERE id=%s", (id,))
            row = cur.fetchone()
            asaas_subscription_id = row[0] if row else None

            if asaas_subscription_id:
                patch_data = {"value": float(valor), "cycle": frequencia}
                if data_inicio:
                    patch_data["nextDueDate"] = data_inicio
                if data_fim:
                    patch_data["endDate"] = data_fim

                resp = requests.post(
                    f"{Config.ASAAS_BASE_URL}/subscriptions/{asaas_subscription_id}",
                    headers={"access_token": Config.ASAAS_API_KEY},
                    json=patch_data,
                    timeout=30
                )
                if resp.status_code not in (200, 201):
                    resp = requests.put(
                        f"{Config.ASAAS_BASE_URL}/subscriptions/{asaas_subscription_id}",
                        headers={"access_token": Config.ASAAS_API_KEY},
                        json=patch_data,
                        timeout=30
                    )
                    if resp.status_code not in (200, 201):
                        flash(f"Locação atualizada, mas falhou no Asaas: {resp.text}", "warning")
                    else:
                        flash("Locação e assinatura atualizadas!", "success")
                else:
                    flash("Locação e assinatura atualizadas!", "success")
            else:
                flash("Locação atualizada (sem assinatura Asaas).", "success")

            conn.commit()
        except Exception as e:
            conn.rollback()
            flash(f"Erro ao atualizar locação: {e}", "danger")
        finally:
            cur.close()
            conn.close()
        return redirect(url_for("locacoes.editar_locacao", id=id))

    # GET
    cur.execute("SELECT id, cliente_id, moto_id, data_inicio, data_fim, valor, frequencia_pagamento, observacoes, asaas_subscription_id FROM locacoes WHERE id=%s", (id,))
    locacao = cur.fetchone()

    cur.execute("""
        SELECT id, asaas_payment_id, status, valor, valor_pago, boleto_url,
               descricao, data_vencimento, data_pagamento
        FROM boletos WHERE locacao_id=%s
        ORDER BY data_vencimento DESC NULLS LAST, id DESC
    """, (id,))
    boletos = cur.fetchall()

    cur.close()
    conn.close()
    return render_template("editar_locacao.html", locacao=locacao, boletos=boletos)

# ==== Listar locações canceladas ====
@locacoes_bp.route("/canceladas")
@login_required
def canceladas():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT l.id, l.data_inicio, l.data_fim, l.valor, l.frequencia_pagamento,
               l.pagamento_status, l.valor_pago, l.asaas_subscription_id, l.boleto_url,
               c.nome AS cliente_nome, m.modelo AS moto_modelo, m.placa AS moto_placa
        FROM locacoes l
        JOIN clientes c ON l.cliente_id = c.id
        JOIN motos m ON l.moto_id = m.id
        WHERE l.cancelado = TRUE
        ORDER BY l.data_inicio DESC
    """)
    locacoes = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("locacoes_canceladas.html", locacoes=locacoes)

# ==== Cancelar locação específica ====
@locacoes_bp.route("/<int:id>/cancelar", methods=["POST"])
@login_required
def cancelar_locacao(id):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT asaas_subscription_id, moto_id FROM locacoes WHERE id=%s", (id,))
        row = cur.fetchone()
        if not row:
            flash("Locação não encontrada.", "danger")
            return redirect(url_for("locacoes.listar_locacoes"))

        asaas_subscription_id, moto_id = row[0], row[1]

        # Cancela assinatura no Asaas se existir
        if asaas_subscription_id:
            resp = requests.post(
                f"{Config.ASAAS_BASE_URL}/subscriptions/{asaas_subscription_id}/cancel",
                headers={"access_token": Config.ASAAS_API_KEY},
                timeout=30
            )
            if resp.status_code not in (200, 201):
                flash(f"Falha ao cancelar assinatura no Asaas: {resp.text}", "warning")

        # Cancela locação localmente
        hoje = dt.date.today().strftime("%Y-%m-%d")
        cur.execute("UPDATE locacoes SET cancelado=TRUE, data_fim=%s WHERE id=%s", (hoje, id))
        cur.execute("UPDATE motos SET disponivel=TRUE WHERE id=%s", (moto_id,))
        conn.commit()
        flash("Locação cancelada!", "info")

    except psycopg2.Error as e:
        conn.rollback()
        motivo = e.pgerror or str(e)
        detalhe = getattr(e.diag, "message_detail", "")
        if detalhe:
            flash(f"Erro ao cancelar locação: {detalhe}", "danger")
        else:
            flash(f"Erro ao cancelar locação: {motivo}", "danger")

    except Exception as e:
        conn.rollback()
        flash(f"Erro inesperado ao cancelar locação: {str(e)}", "danger")

    finally:
        cur.close()
        conn.close()
    return redirect(url_for("locacoes.listar_locacoes"))

# ==== Sincronizar boletos manualmente ====
@locacoes_bp.route("/<int:id>/sincronizar_boletos", methods=["GET"])
@login_required
def sincronizar_boletos_manual(id):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT asaas_subscription_id FROM locacoes WHERE id=%s", (id,))
        row = cur.fetchone()
        if not row or not row[0]:
            flash("Assinatura Asaas não vinculada à locação.", "warning")
            return redirect(url_for("locacoes.editar_locacao", id=id))

        sub_id = row[0]
        url = f"{Config.ASAAS_BASE_URL}/payments?subscription={sub_id}&limit=100"
        resp = requests.get(url, headers={"access_token": Config.ASAAS_API_KEY}, timeout=30)
        if resp.status_code not in (200, 201):
            flash(f"Erro ao consultar boletos no Asaas: {resp.text}", "danger")
            return redirect(url_for("locacoes.editar_locacao", id=id))

        data = resp.json()
        items = data.get("data", []) if isinstance(data, dict) else []

        inseridos, atualizados = 0, 0
        for p in items:
            asaas_payment_id = p.get("id")
            status = p.get("status")
            valor = p.get("value")
            net_value = p.get("netValue")
            boleto_url = p.get("bankSlipUrl")
            descricao = p.get("description")
            due_date = p.get("dueDate")
            payment_date = p.get("paymentDate")

            cur.execute("SELECT id FROM boletos WHERE asaas_payment_id=%s", (asaas_payment_id,))
            existe = cur.fetchone()
            if existe:
                cur.execute("""
                    UPDATE boletos
                    SET status=%s, valor=%s, valor_pago=%s, boleto_url=%s,
                        descricao=%s, data_vencimento=%s, data_pagamento=%s
                    WHERE asaas_payment_id=%s
                """, (status, valor, net_value, boleto_url,
                      descricao, due_date, payment_date, asaas_payment_id))
                atualizados += 1
            else:
                cur.execute("""
                    INSERT INTO boletos (locacao_id, asaas_payment_id, status, valor,
                                       valor_pago, boleto_url, descricao,
                                       data_vencimento, data_pagamento)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """, (id, asaas_payment_id, status, valor, net_value,
                      boleto_url, descricao, due_date, payment_date))
                inseridos += 1

        conn.commit()
        flash(f"Boletos sincronizados! Inseridos: {inseridos}, Atualizados: {atualizados}.", "success")
    except Exception as e:
        conn.rollback()
        flash(f"Erro ao sincronizar boletos: {e}", "danger")
    finally:
        cur.close()
        conn.close()
    return redirect(url_for("locacoes.editar_locacao", id=id))


# ==== Servir PDF de contratos ====
from flask import current_app, send_from_directory, abort
import os

@locacoes_bp.route("/contratos/<path:filename>")
@login_required
def uploaded_contract(filename):
    base = current_app.config.get("UPLOAD_FOLDER", "uploads")
    directory = os.path.join(base, "contratos")

    # proteção contra path traversal
    if ".." in filename or filename.startswith("/"):
        abort(400)

    return send_from_directory(directory, filename, as_attachment=False)