import datetime as dt
from flask import Blueprint, render_template
from flask_login import login_required
from database import get_db_connection

dashboard_bp = Blueprint("dashboard", __name__)

@dashboard_bp.route("/")
@login_required
def home():
    hoje = dt.date.today()
    primeiro_dia_mes = hoje.replace(day=1)

    conn = get_db_connection()
    cur = conn.cursor()

    # Função auxiliar para extrair valor do cursor (dict ou tupla)
    def get_count(cursor_result):
        if cursor_result is None:
            return 0
        if isinstance(cursor_result, dict):
            return cursor_result.get('count', 0) or 0
        return cursor_result[0] if cursor_result else 0

    # Contagens básicas
    cur.execute("SELECT COUNT(*) AS count FROM clientes")
    total_clientes = get_count(cur.fetchone())

    cur.execute("SELECT COUNT(*) AS count FROM motos")
    total_motos = get_count(cur.fetchone())

    cur.execute("SELECT COUNT(*) AS count FROM locacoes WHERE cancelado=FALSE")
    locacoes_ativas = get_count(cur.fetchone())

    cur.execute("SELECT COUNT(*) AS count FROM locacoes WHERE cancelado=TRUE")
    locacoes_canceladas = get_count(cur.fetchone())

    # Boletos pendentes e pagos
    cur.execute("SELECT COUNT(*) AS count FROM boletos WHERE status IN ('PENDING','OVERDUE')")
    boletos_pendentes = get_count(cur.fetchone())

    cur.execute("SELECT COUNT(*) AS count FROM boletos WHERE status IN ('RECEIVED','CONFIRMED','RECEIVED_IN_CASH')")
    boletos_pagados = get_count(cur.fetchone())

    # Receita do mês (somatório dos pagos no mês atual)
    cur.execute("""
        SELECT COALESCE(SUM(COALESCE(valor_pago,0)),0) AS receita
        FROM boletos
        WHERE status IN ('RECEIVED','CONFIRMED','RECEIVED_IN_CASH')
          AND data_pagamento >= %s
          AND data_pagamento < %s
    """, (primeiro_dia_mes, (primeiro_dia_mes.replace(day=28) + dt.timedelta(days=4)).replace(day=1)))
    
    result = cur.fetchone()
    if isinstance(result, dict):
        receita_mes = result.get('receita', 0) or 0
    else:
        receita_mes = result[0] if result else 0

    # Inadimplentes (boletos vencidos sem pagamento)
    cur.execute("SELECT COUNT(*) AS count FROM boletos WHERE status='OVERDUE'")
    inadimplentes = get_count(cur.fetchone())

    cur.close()
    conn.close()

    metrics = {
        "total_clientes": total_clientes,
        "total_motos": total_motos,
        "locacoes_ativas": locacoes_ativas,
        "locacoes_canceladas": locacoes_canceladas,
        "boletos_pendentes": boletos_pendentes,
        "boletos_pagados": boletos_pagados,
        "receita_mes": receita_mes,
        "inadimplentes": inadimplentes,
        "hoje": hoje.strftime("%Y-%m-%d"),
    }

    return render_template("dashboard.html", metrics=metrics)