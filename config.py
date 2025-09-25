import os

class Config:
    # Secret da aplicação
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret")

    # Banco de dados
    DATABASE_URL = os.getenv("DATABASE_URL")  # usado no Render
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_NAME = os.getenv("DB_NAME", "motorental")
    DB_USER = os.getenv("DB_USER", "postgres")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")
    DB_SSLMODE = os.getenv("DB_SSLMODE", "require")

    # Asaas
    ASAAS_API_KEY = os.getenv("ASAAS_API_KEY")
    ASAAS_BASE_URL = os.getenv("ASAAS_BASE_URL", "https://sandbox.asaas.com/api/v3")
    ASAAS_WEBHOOK_SECRET = os.getenv("ASAAS_WEBHOOK_SECRET")