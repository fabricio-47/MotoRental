-- Schema MotoRental (com tabela boletos para histórico completo)

CREATE TABLE clientes (
    id SERIAL PRIMARY KEY,
    nome TEXT NOT NULL,
    email TEXT NOT NULL,
    telefone TEXT NOT NULL,
    cpf VARCHAR(20),
    endereco TEXT,
    data_nascimento DATE,
    observacoes TEXT,
    habilitacao_arquivo VARCHAR(255),
    asaas_id VARCHAR(255) -- ID único do cliente no Asaas
);

CREATE TABLE motos (
    id SERIAL PRIMARY KEY,
    placa VARCHAR(20) NOT NULL,
    modelo TEXT NOT NULL,
    ano INTEGER,
    disponivel BOOLEAN DEFAULT TRUE,
    imagem VARCHAR(255),
    documento_arquivo VARCHAR(255)
);

CREATE TABLE locacoes (
    id SERIAL PRIMARY KEY,
    cliente_id INTEGER NOT NULL REFERENCES clientes(id) ON DELETE CASCADE,
    moto_id INTEGER NOT NULL REFERENCES motos(id) ON DELETE CASCADE,
    data_inicio DATE NOT NULL,
    data_fim DATE,
    cancelado BOOLEAN DEFAULT FALSE,
    observacoes TEXT,
    contrato_pdf VARCHAR(255),

    -- integração com Asaas
    valor NUMERIC(10,2),
    boleto_url TEXT,
    pagamento_status VARCHAR(50),
    valor_pago NUMERIC(10,2),
    data_pagamento DATE,
    asaas_payment_id VARCHAR(255),

    -- frequência de pagamento
    frequencia_pagamento VARCHAR(20)
);

-- Nova tabela para histórico completo de boletos
CREATE TABLE boletos (
    id SERIAL PRIMARY KEY,
    locacao_id INTEGER NOT NULL REFERENCES locacoes(id) ON DELETE CASCADE,
    asaas_payment_id VARCHAR(255) UNIQUE NOT NULL,
    status VARCHAR(50) DEFAULT 'PENDING',
    valor NUMERIC(10,2),
    valor_pago NUMERIC(10,2),
    boleto_url TEXT,
    descricao TEXT,
    data_vencimento DATE,
    data_pagamento DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE moto_imagens (
    id SERIAL PRIMARY KEY,
    moto_id INTEGER NOT NULL REFERENCES motos(id) ON DELETE CASCADE,
    arquivo TEXT NOT NULL,
    data_upload TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE servicos_locacao (
    id SERIAL PRIMARY KEY,
    locacao_id INTEGER NOT NULL REFERENCES locacoes(id) ON DELETE CASCADE,
    descricao TEXT NOT NULL,
    valor NUMERIC(10,2),
    data_servico DATE,
    quilometragem INTEGER
);

CREATE TABLE usuarios (
    id SERIAL PRIMARY KEY,
    username VARCHAR(255) NOT NULL UNIQUE,
    email TEXT NOT NULL,
    senha TEXT NOT NULL,
    is_admin BOOLEAN DEFAULT FALSE
);

-- Índices para performance
CREATE INDEX idx_boletos_locacao_id ON boletos(locacao_id);
CREATE INDEX idx_boletos_status ON boletos(status);
CREATE INDEX idx_boletos_due_date ON boletos(data_vencimento);
CREATE INDEX idx_locacoes_cliente_id ON locacoes(cliente_id);
CREATE INDEX idx_locacoes_moto_id ON locacoes(moto_id);