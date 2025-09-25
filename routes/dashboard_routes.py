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

    # Contagens básicas
    cur.execute("SELECT COUNT(*) FROM clientes")
    total_clientes = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM motos")
    total_motos = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM locacoes WHERE cancelado=FALSE")
    locacoes_ativas = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM locacoes WHERE cancelado=TRUE")
    locacoes_canceladas = cur.fetchone()[0]

    # Boletos pendentes e pagos
    cur.execute("SELECT COUNT(*) FROM boletos WHERE status IN ('PENDING','OVERDUE')")
    boletos_pendentes = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM boletos WHERE status IN ('RECEIVED','CONFIRMED','RECEIVED_IN_CASH')")
    boletos_pagados = cur.fetchone()[0]

    # Receita do mês (somatório dos pagos no mês atual)
    cur.execute("""
        SELECT COALESCE(SUM(COALESCE(valor_pago,0)),0)
        FROM boletos
        WHERE status IN ('RECEIVED','CONFIRMED','RECEIVED_IN_CASH')
          AND data_pagamento >= %s
          AND data_pagamento < %s
    """, (primeiro_dia_mes, (primeiro_dia_mes.replace(day=28) + dt.timedelta(days=4)).replace(day=1)))
    receita_mes = cur.fetchone()[0] or 0

    # Inadimplentes (boletos vencidos sem pagamento)
    cur.execute("""
        SELECT COUNT(*)
        FROM boletos
        WHERE status='OVERDUE'
    """)
    inadimplentes = cur.fetchone()[0]

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