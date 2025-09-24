-- Schema MotoRental Completo e Robusto
-- Versão otimizada com constraints, índices e triggers

-- Extensão para emails case-insensitive
CREATE EXTENSION IF NOT EXISTS citext;

-- Função para atualizar updated_at automaticamente
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = CURRENT_TIMESTAMP;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Tabela de usuários
CREATE TABLE usuarios (
    id SERIAL PRIMARY KEY,
    username citext NOT NULL UNIQUE,
    email citext NOT NULL UNIQUE,
    senha TEXT NOT NULL,
    is_admin BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tabela de clientes
CREATE TABLE clientes (
    id SERIAL PRIMARY KEY,
    nome TEXT NOT NULL,
    email citext NOT NULL UNIQUE,
    telefone TEXT NOT NULL,
    cpf VARCHAR(20) UNIQUE,
    endereco TEXT,
    data_nascimento DATE,
    observacoes TEXT,
    habilitacao_arquivo VARCHAR(255),
    asaas_id VARCHAR(255) UNIQUE, -- ID único do cliente no Asaas
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Constraints
    CONSTRAINT chk_clientes_cpf_format CHECK (cpf ~ '^\d{3}\.\d{3}\.\d{3}-\d{2}$' OR cpf ~ '^\d{11}$' OR cpf IS NULL)
);

-- Tabela de motos
CREATE TABLE motos (
    id SERIAL PRIMARY KEY,
    placa VARCHAR(20) NOT NULL UNIQUE,
    modelo TEXT NOT NULL,
    ano INTEGER,
    disponivel BOOLEAN DEFAULT TRUE,
    imagem VARCHAR(255),
    documento_arquivo VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Constraints
    CONSTRAINT chk_motos_ano CHECK (ano IS NULL OR (ano >= 1900 AND ano <= EXTRACT(YEAR FROM CURRENT_DATE) + 1)),
    CONSTRAINT chk_motos_placa_format CHECK (placa ~ '^[A-Z]{3}-?\d{4}$' OR placa ~ '^[A-Z]{3}\d[A-Z]\d{2}$')
);

-- Tabela de locações
CREATE TABLE locacoes (
    id SERIAL PRIMARY KEY,
    cliente_id INTEGER NOT NULL REFERENCES clientes(id) ON DELETE CASCADE,
    moto_id INTEGER NOT NULL REFERENCES motos(id) ON DELETE CASCADE,
    data_inicio DATE NOT NULL,
    data_fim DATE,
    cancelado BOOLEAN DEFAULT FALSE,
    observacoes TEXT,
    contrato_pdf VARCHAR(255),
    asaas_subscription_id VARCHAR(255) UNIQUE,
    
    -- Integração com Asaas
    valor NUMERIC(12,2),
    boleto_url TEXT,
    pagamento_status VARCHAR(50) DEFAULT 'PENDING',
    valor_pago NUMERIC(12,2) DEFAULT 0,
    data_pagamento DATE,
    asaas_payment_id VARCHAR(255),
    
    -- Frequência de pagamento
    frequencia_pagamento VARCHAR(20) DEFAULT 'MONTHLY',
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Constraints
    CONSTRAINT chk_locacoes_datas CHECK (data_fim IS NULL OR data_fim >= data_inicio),
    CONSTRAINT chk_locacoes_valor CHECK (valor IS NULL OR valor >= 0),
    CONSTRAINT chk_locacoes_valor_pago CHECK (valor_pago IS NULL OR valor_pago >= 0),
    CONSTRAINT chk_locacoes_freq CHECK (frequencia_pagamento IN ('WEEKLY','MONTHLY','BIWEEKLY','QUARTERLY','YEARLY','CUSTOM')),
    CONSTRAINT chk_locacoes_status CHECK (pagamento_status IN (
        'PENDING','RECEIVED','CONFIRMED','OVERDUE','CANCELED','REFUNDED','CHARGEBACK','RECEIVED_IN_CASH'
    ))
);

-- Tabela de histórico completo de boletos
CREATE TABLE boletos (
    id SERIAL PRIMARY KEY,
    locacao_id INTEGER NOT NULL REFERENCES locacoes(id) ON DELETE CASCADE,
    asaas_payment_id VARCHAR(255) UNIQUE NOT NULL,
    status VARCHAR(50) DEFAULT 'PENDING',
    valor NUMERIC(12,2),
    valor_pago NUMERIC(12,2) DEFAULT 0,
    boleto_url TEXT,
    descricao TEXT,
    data_vencimento DATE,
    data_pagamento DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Constraints
    CONSTRAINT chk_boletos_valor CHECK (valor IS NULL OR valor >= 0),
    CONSTRAINT chk_boletos_valor_pago CHECK (valor_pago IS NULL OR valor_pago >= 0),
    CONSTRAINT chk_boletos_status CHECK (status IN (
        'PENDING','RECEIVED','CONFIRMED','OVERDUE','CANCELED','REFUNDED','CHARGEBACK','RECEIVED_IN_CASH'
    )),
    CONSTRAINT chk_boletos_vencimento CHECK (data_vencimento >= CURRENT_DATE - INTERVAL '1 year')
);

-- Tabela de imagens das motos
CREATE TABLE moto_imagens (
    id SERIAL PRIMARY KEY,
    moto_id INTEGER NOT NULL REFERENCES motos(id) ON DELETE CASCADE,
    arquivo TEXT NOT NULL,
    data_upload TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tabela de serviços da locação
CREATE TABLE servicos_locacao (
    id SERIAL PRIMARY KEY,
    locacao_id INTEGER NOT NULL REFERENCES locacoes(id) ON DELETE CASCADE,
    descricao TEXT NOT NULL,
    valor NUMERIC(12,2),
    data_servico DATE DEFAULT CURRENT_DATE,
    quilometragem INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Constraints
    CONSTRAINT chk_servicos_valor CHECK (valor IS NULL OR valor >= 0),
    CONSTRAINT chk_servicos_km CHECK (quilometragem IS NULL OR quilometragem >= 0)
);

-- ÍNDICES PARA PERFORMANCE

-- Índices para clientes
CREATE INDEX idx_clientes_cpf ON clientes(cpf);
CREATE INDEX idx_clientes_email ON clientes(email);
CREATE INDEX idx_clientes_asaas ON clientes(asaas_id);
CREATE INDEX idx_clientes_nome ON clientes(nome);

-- Índices para motos
CREATE INDEX idx_motos_placa ON motos(placa);
CREATE INDEX idx_motos_disponivel ON motos(disponivel);
CREATE INDEX idx_motos_modelo ON motos(modelo);

-- Índices para locações
CREATE INDEX idx_locacoes_cliente_id ON locacoes(cliente_id);
CREATE INDEX idx_locacoes_moto_id ON locacoes(moto_id);
CREATE INDEX idx_locacoes_subscription ON locacoes(asaas_subscription_id);
CREATE INDEX idx_locacoes_payment_id ON locacoes(asaas_payment_id);
CREATE INDEX idx_locacoes_pagamento_status ON locacoes(pagamento_status);
CREATE INDEX idx_locacoes_cancelado_data ON locacoes(cancelado, data_inicio);
CREATE INDEX idx_locacoes_data_inicio ON locacoes(data_inicio);
CREATE INDEX idx_locacoes_data_fim ON locacoes(data_fim);

-- Índices para boletos
CREATE INDEX idx_boletos_locacao_id ON boletos(locacao_id);
CREATE INDEX idx_boletos_status ON boletos(status);
CREATE INDEX idx_boletos_due_date ON boletos(data_vencimento);
CREATE INDEX idx_boletos_payment_id ON boletos(asaas_payment_id);
CREATE INDEX idx_boletos_created_at ON boletos(created_at);

-- Índices para moto_imagens
CREATE INDEX idx_moto_imagens_moto_id ON moto_imagens(moto_id);

-- Índices para servicos_locacao
CREATE INDEX idx_servicos_locacao_id ON servicos_locacao(locacao_id);
CREATE INDEX idx_servicos_data ON servicos_locacao(data_servico);

-- Índices para usuarios
CREATE INDEX idx_usuarios_username ON usuarios(username);
CREATE INDEX idx_usuarios_email ON usuarios(email);

-- TRIGGERS PARA UPDATED_AT

CREATE TRIGGER trg_usuarios_updated 
    BEFORE UPDATE ON usuarios
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_clientes_updated 
    BEFORE UPDATE ON clientes
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_motos_updated 
    BEFORE UPDATE ON motos
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_locacoes_updated 
    BEFORE UPDATE ON locacoes
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_boletos_updated 
    BEFORE UPDATE ON boletos
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_servicos_updated 
    BEFORE UPDATE ON servicos_locacao
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- VIEWS ÚTEIS PARA RELATÓRIOS

-- View para locações ativas com informações completas
CREATE VIEW v_locacoes_ativas AS
SELECT 
    l.id,
    l.data_inicio,
    l.data_fim,
    l.valor,
    l.pagamento_status,
    l.frequencia_pagamento,
    c.nome as cliente_nome,
    c.email as cliente_email,
    c.telefone as cliente_telefone,
    c.cpf as cliente_cpf,
    m.placa as moto_placa,
    m.modelo as moto_modelo,
    m.ano as moto_ano,
    COUNT(b.id) as total_boletos,
    SUM(CASE WHEN b.status = 'RECEIVED' THEN b.valor_pago ELSE 0 END) as total_pago
FROM locacoes l
JOIN clientes c ON l.cliente_id = c.id
JOIN motos m ON l.moto_id = m.id
LEFT JOIN boletos b ON l.id = b.locacao_id
WHERE l.cancelado = FALSE
GROUP BY l.id, c.id, m.id;

-- View para boletos em atraso
CREATE VIEW v_boletos_vencidos AS
SELECT 
    b.*,
    l.cliente_id,
    c.nome as cliente_nome,
    c.telefone as cliente_telefone,
    m.placa as moto_placa,
    CURRENT_DATE - b.data_vencimento as dias_atraso
FROM boletos b
JOIN locacoes l ON b.locacao_id = l.id
JOIN clientes c ON l.cliente_id = c.id
JOIN motos m ON l.moto_id = m.id
WHERE b.status IN ('PENDING', 'OVERDUE') 
  AND b.data_vencimento < CURRENT_DATE;

-- View para dashboard financeiro
CREATE VIEW v_dashboard_financeiro AS
SELECT 
    COUNT(CASE WHEN b.status = 'PENDING' AND b.data_vencimento >= CURRENT_DATE THEN 1 END) as boletos_pendentes,
    COUNT(CASE WHEN b.status = 'OVERDUE' OR (b.status = 'PENDING' AND b.data_vencimento < CURRENT_DATE) THEN 1 END) as boletos_vencidos,
    COUNT(CASE WHEN b.status = 'RECEIVED' THEN 1 END) as boletos_pagos,
    SUM(CASE WHEN b.status = 'PENDING' AND b.data_vencimento >= CURRENT_DATE THEN b.valor ELSE 0 END) as valor_a_receber,
    SUM(CASE WHEN b.status = 'OVERDUE' OR (b.status = 'PENDING' AND b.data_vencimento < CURRENT_DATE) THEN b.valor ELSE 0 END) as valor_em_atraso,
    SUM(CASE WHEN b.status = 'RECEIVED' THEN b.valor_pago ELSE 0 END) as valor_recebido_total,
    SUM(CASE WHEN b.status = 'RECEIVED' AND DATE_TRUNC('month', b.data_pagamento) = DATE_TRUNC('month', CURRENT_DATE) THEN b.valor_pago ELSE 0 END) as valor_recebido_mes
FROM boletos b;


-- COMENTÁRIOS FINAIS
COMMENT ON TABLE clientes IS 'Tabela de clientes com integração Asaas';
COMMENT ON TABLE motos IS 'Tabela de motocicletas disponíveis para locação';
COMMENT ON TABLE locacoes IS 'Tabela principal de locações com dados de pagamento';
COMMENT ON TABLE boletos IS 'Histórico completo de todos os boletos gerados';
COMMENT ON TABLE servicos_locacao IS 'Serviços adicionais cobrados nas locações';
COMMENT ON VIEW v_locacoes_ativas IS 'View com locações ativas e resumo financeiro';
COMMENT ON VIEW v_boletos_vencidos IS 'View com boletos em atraso para cobrança';
COMMENT ON VIEW v_dashboard_financeiro IS 'View com métricas financeiras para dashboard';