-- ==========================================================
-- SCHEMA: Sistema de aluguel de motos
-- OBS: Esse script APAGA todas as tabelas (modo testes/dev)
-- ==========================================================

-- Remove tabelas na ordem certa (dependências primeiro)
DROP TABLE IF EXISTS servicos_locacao CASCADE;
DROP TABLE IF EXISTS moto_imagens CASCADE;
DROP TABLE IF EXISTS locacoes CASCADE;
DROP TABLE IF EXISTS clientes CASCADE;
DROP TABLE IF EXISTS motos CASCADE;
DROP TABLE IF EXISTS usuarios CASCADE;

-- ==========================================================
-- Usuários (sistema / admin)
-- ==========================================================
CREATE TABLE usuarios (
    id SERIAL PRIMARY KEY,
    username VARCHAR(100) UNIQUE NOT NULL, -- login
    email TEXT UNIQUE NOT NULL,            -- email único
    senha TEXT NOT NULL,                   -- senha hash
    is_admin BOOLEAN DEFAULT FALSE         -- flag admin/simples
);

-- ==========================================================
-- Motos
-- ==========================================================
CREATE TABLE motos (
    id SERIAL PRIMARY KEY,
    placa TEXT NOT NULL UNIQUE,
    modelo TEXT NOT NULL,
    ano INTEGER NOT NULL,
    disponivel BOOLEAN DEFAULT TRUE,
    imagem VARCHAR(255)                    -- 🚀 imagem principal da moto
);

-- ==========================================================
-- Clientes
-- ==========================================================
CREATE TABLE clientes (
    id SERIAL PRIMARY KEY,
    nome TEXT NOT NULL,
    email TEXT,
    telefone TEXT,
    cpf VARCHAR(14),
    endereco TEXT,
    data_nascimento DATE,
    observacoes TEXT,
    habilitacao_arquivo VARCHAR(255)       -- 🚀 arquivo da CNH (imagem/pdf)
);

-- ==========================================================
-- Locações
-- ==========================================================
CREATE TABLE locacoes (
    id SERIAL PRIMARY KEY,
    cliente_id INTEGER NOT NULL REFERENCES clientes (id) ON DELETE CASCADE,
    moto_id INTEGER NOT NULL REFERENCES motos (id) ON DELETE CASCADE,
    data_inicio DATE NOT NULL,
    data_fim DATE,
    cancelado BOOLEAN DEFAULT FALSE,       -- se TRUE = locação cancelada
    observacoes TEXT,                      -- anotações internas
    contrato_pdf VARCHAR(255)              -- contrato da locação (PDF)
);

-- ==========================================================
-- Serviços feitos durante uma locação
-- ==========================================================
CREATE TABLE servicos_locacao (
    id SERIAL PRIMARY KEY,
    locacao_id INTEGER NOT NULL REFERENCES locacoes (id) ON DELETE CASCADE,
    descricao TEXT NOT NULL,               -- Ex.: troca de óleo, manutenção, multa
    valor DECIMAL(10,2) DEFAULT 0,         -- custo ou taxa
    data_servico DATE DEFAULT CURRENT_DATE -- data do serviço
);

-- ==========================================================
-- Imagens das motos adicionais
-- ==========================================================
CREATE TABLE moto_imagens (
    id SERIAL PRIMARY KEY,
    moto_id INTEGER NOT NULL REFERENCES motos (id) ON DELETE CASCADE,
    arquivo TEXT NOT NULL,                 -- filename no servidor
    data_upload TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);