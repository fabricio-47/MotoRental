# create_admin.py
import os
import psycopg2
from werkzeug.security import generate_password_hash

def create_admin():
    # pega a URL do Postgres (no Render vem da env var DATABASE_URL)
    database_url = os.environ.get("DATABASE_URL")

    if not database_url:
        print("❌ ERRO: DATABASE_URL não está configurado")
        return

    # conecta no banco
    conn = psycopg2.connect(database_url)
    cur = conn.cursor()

    # cria usuário admin fixo
    email = "admin@admin.com"
    senha = "123"

    cur.execute("DELETE FROM usuarios WHERE email = %s", (email,))
    cur.execute(
        "INSERT INTO usuarios (email, senha) VALUES (%s, %s)",
        (email, generate_password_hash(senha))
    )

    conn.commit()
    cur.close()
    conn.close()

    print(f"✅ Usuário admin criado -> email: {email} | senha: {senha}")

if __name__ == "__main__":
    create_admin()