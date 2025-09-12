-- Apaga tabelas antigas (somente no período de testes!)
DROP TABLE IF EXISTS usuarios CASCADE;
DROP TABLE IF EXISTS motos CASCADE;
DROP TABLE IF EXISTS clientes CASCADE;
DROP TABLE IF EXISTS locacoes CASCADE;

-- Usuários (login/admin)
CREATE TABLE usuarios (
    id SERIAL PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    senha TEXT NOT NULL
);

-- Motos
CREATE TABLE motos (
    id SERIAL PRIMARY KEY,
    placa TEXT NOT NULL UNIQUE,
    modelo TEXT NOT NULL,
    ano INTEGER NOT NULL,
    disponivel BOOLEAN DEFAULT TRUE
);

-- Clientes com mais informações
CREATE TABLE clientes (
    id SERIAL PRIMARY KEY,
    nome TEXT NOT NULL,
    email TEXT,
    telefone TEXT,
    cpf VARCHAR(14),
    endereco TEXT,
    data_nascimento DATE,
    observacoes TEXT
);

-- Locações com flag de cancelamento
CREATE TABLE locacoes (
    id SERIAL PRIMARY KEY,
    cliente_id INTEGER NOT NULL REFERENCES clientes (id) ON DELETE CASCADE,
    moto_id INTEGER NOT NULL REFERENCES motos (id) ON DELETE CASCADE,
    data_inicio DATE NOT NULL,
    data_fim DATE,
    cancelado BOOLEAN DEFAULT FALSE -- se TRUE, aluguel cancelado
);