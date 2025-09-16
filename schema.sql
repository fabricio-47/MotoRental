-- Apaga tabelas antigas (somente no período de testes!)
DROP TABLE IF EXISTS servicos_locacao CASCADE;
DROP TABLE IF EXISTS moto_imagens CASCADE;
DROP TABLE IF EXISTS usuarios CASCADE;
DROP TABLE IF EXISTS motos CASCADE;
DROP TABLE IF EXISTS clientes CASCADE;
DROP TABLE IF EXISTS locacoes CASCADE;

-- Usuários (login/admin)
CREATE TABLE usuarios (
    id SERIAL PRIMARY KEY,
    username VARCHAR(100) UNIQUE NOT NULL, -- novo campo para login por usuário
    email TEXT UNIQUE NOT NULL,            -- email continua único
    senha TEXT NOT NULL,                   -- senha hash (bcrypt/werkzeug)
    is_admin BOOLEAN DEFAULT FALSE         -- flag admin
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

-- Locações com flag de cancelamento + observações + upload contrato
CREATE TABLE locacoes (
    id SERIAL PRIMARY KEY,
    cliente_id INTEGER NOT NULL REFERENCES clientes (id) ON DELETE CASCADE,
    moto_id INTEGER NOT NULL REFERENCES motos (id) ON DELETE CASCADE,
    data_inicio DATE NOT NULL,
    data_fim DATE,
    cancelado BOOLEAN DEFAULT FALSE,   -- se TRUE, aluguel cancelado
    observacoes TEXT,                  -- novas anotações internas
    contrato_pdf VARCHAR(255)          -- filename do contrato (PDF)
);

-- Serviços feitos durante uma locação
CREATE TABLE servicos_locacao (
    id SERIAL PRIMARY KEY,
    locacao_id INTEGER NOT NULL REFERENCES locacoes (id) ON DELETE CASCADE,
    descricao TEXT NOT NULL,               -- Ex: troca de óleo, revisão, multa
    valor DECIMAL(10,2) DEFAULT 0,         -- custo ou taxa do serviço
    data_servico DATE DEFAULT CURRENT_DATE -- data do serviço
);

-- Imagens das motos
CREATE TABLE moto_imagens (
    id SERIAL PRIMARY KEY,
    moto_id INTEGER NOT NULL REFERENCES motos (id) ON DELETE CASCADE,
    arquivo TEXT NOT NULL,       -- caminho/filename no servidor
    data_upload TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE servicos_locacao (
    id SERIAL PRIMARY KEY,
    locacao_id INTEGER NOT NULL REFERENCES locacoes (id) ON DELETE CASCADE,
    descricao TEXT NOT NULL,               -- Ex: "Troca de óleo", "Manutenção freios"
    valor DECIMAL(10,2) DEFAULT 0,         -- opcional: custo do serviço
    data_servico DATE DEFAULT CURRENT_DATE -- quando foi feito
);