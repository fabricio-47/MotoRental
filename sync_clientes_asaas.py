# sync_clientes_asaas.py
import os
import requests
import psycopg2
import psycopg2.extras
import time
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

ASAAS_API_KEY = os.environ.get("ASAAS_API_KEY")
ASAAS_BASE_URL = os.environ.get("ASAAS_BASE_URL", "https://www.asaas.com/api/v3")
HEADERS = {"accept": "application/json", "content-type": "application/json", "access_token": ASAAS_API_KEY}

def normalize_response_list(resp_json):
    # handles different shapes: list, {"data":[...]}, {"items":[...]}
    if isinstance(resp_json, list):
        return resp_json
    if isinstance(resp_json, dict):
        for k in ("data", "items", "customers"):
            if k in resp_json and isinstance(resp_json[k], list):
                return resp_json[k]
    return []

def buscar_cliente_asaas_por_cpf(cpf):
    try:
        r = requests.get(f"{ASAAS_BASE_URL}/customers", headers=HEADERS, params={"cpfCnpj": cpf})
        r.raise_for_status()
        itens = normalize_response_list(r.json())
        if itens:
            return itens[0]
    except Exception as e:
        logging.exception("Erro ao buscar cliente por CPF %s: %s", cpf, e)
    return None

def buscar_cliente_asaas_por_email(email):
    try:
        r = requests.get(f"{ASAAS_BASE_URL}/customers", headers=HEADERS, params={"email": email})
        r.raise_for_status()
        itens = normalize_response_list(r.json())
        if itens:
            return itens[0]
    except Exception as e:
        logging.exception("Erro ao buscar cliente por email %s: %s", email, e)
    return None

def criar_cliente_asaas(nome, email, cpf, telefone):
    payload = {"name": nome, "email": email, "cpfCnpj": cpf, "mobilePhone": telefone}
    r = requests.post(f"{ASAAS_BASE_URL}/customers", headers=HEADERS, json=payload)
    r.raise_for_status()
    return r.json()

def sync_clientes(db_conn, dry_run=True, sleep_between=0.2):
    cur = db_conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT id, nome, email, cpf, telefone FROM clientes WHERE asaas_id IS NULL")
    clientes = cur.fetchall()
    logging.info("Encontrados %d clientes sem asaas_id", len(clientes))
    for c in clientes:
        try:
            logging.info("Processando cliente local id=%s nome=%s", c["id"], c["nome"])
            found = None
            if c.get("cpf"):
                found = buscar_cliente_asaas_por_cpf(c["cpf"])
            if not found and c.get("email"):
                found = buscar_cliente_asaas_por_email(c["email"])

            if found:
                asaas_id = found.get("id")
                logging.info("Encontrado no Asaas: id=%s (via busca)", asaas_id)
            else:
                logging.info("Nao encontrado no Asaas — criando...")
                novo = criar_cliente_asaas(c["nome"], c.get("email"), c.get("cpf"), c.get("telefone"))
                asaas_id = novo.get("id")
                logging.info("Criado no Asaas: id=%s", asaas_id)

            if asaas_id:
                if dry_run:
                    logging.info("[dry-run] iria atualizar clientes.id=%s -> asaas_id=%s", c["id"], asaas_id)
                else:
                    cur.execute("UPDATE clientes SET asaas_id = %s WHERE id = %s", (asaas_id, c["id"]))
                    db_conn.commit()
                    logging.info("Atualizado localmente clientes.id=%s -> asaas_id=%s", c["id"], asaas_id)

            time.sleep(sleep_between)  # respeitar rate limits
        except Exception as e:
            logging.exception("Erro ao processar cliente %s: %s", c["id"], e)

    cur.close()

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Não aplica updates no banco (default: True)")
    parser.add_argument("--apply", action="store_true", help="Aplica updates no banco")
    parser.add_argument("--db-url", default=os.environ.get("DATABASE_URL"), help="Database URL")
    args = parser.parse_args()

    if not args.db_url:
        raise SystemExit("DATABASE_URL não encontrado. Exporte a variável ou use --db-url")

    conn = psycopg2.connect(args.db_url)
    try:
        sync_clientes(conn, dry_run=(not args.apply))
    finally:
        conn.close()