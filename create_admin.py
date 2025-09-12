import os
import psycopg2
from werkzeug.security import generate_password_hash

def create_admin():
    # Pega a string de conexão do Postgres (Render/Docker/local)
    database_url = os.environ.get("DATABASE_URL")

    if not database_url:
        print("❌ ERRO: DATABASE_URL não está configurado")
        return

    # Conecta ao banco
    conn = psycopg2.connect(database_url)
    cur = conn.cursor()

    # Dados do admin
    username = "admin"
    email = "admin@admin.com"
    senha = "123"

    # Remove admin antigo (se já existia)
    cur.execute("DELETE FROM usuarios WHERE username = %s OR email = %s", (username, email))

    # Insere novo admin
    cur.execute(
        """
        INSERT INTO usuarios (username, email, senha, is_admin)
        VALUES (%s, %s, %s, %s)
        """,
        (username, email, generate_password_hash(senha), True)
    )

    # Commit
    conn.commit()
    cur.close()
    conn.close()

    print(f"✅ Usuário admin criado -> username: {username} | email: {email} | senha: {senha}")

if __name__ == "__main__":
    create_admin()