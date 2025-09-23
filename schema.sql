-- Schema completo unificado para o banco MotoRental

CREATE TABLE clientes (
    id SERIAL PRIMARY KEY,
    nome TEXT NOT NULL,
    email TEXT NOT NULL,
    telefone TEXT NOT NULL,
    cpf VARCHAR(255),
    endereco TEXT,
    data_nascimento DATE,
    observacoes TEXT,
    habilitacao_arquivo VARCHAR(255),
    asaas_id VARCHAR(255),
    id_asaas VARCHAR(255)
);

CREATE TABLE motos (
    id SERIAL PRIMARY KEY,
    placa TEXT NOT NULL,
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
    boleto_url TEXT,
    url_boleto TEXT,
    id_pagamento_asaas VARCHAR(255),
    status_pagamento VARCHAR(255),
    pagamento_status VARCHAR(255),
    valor_pago NUMERIC,
    data_pagamento TIMESTAMP,
    asaas_payment_id VARCHAR(255)
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
    valor NUMERIC,
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