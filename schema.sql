DROP TABLE IF EXISTS usuarios;
DROP TABLE IF EXISTS motos;
DROP TABLE IF EXISTS clientes;
DROP TABLE IF EXISTS locacoes;

CREATE TABLE usuarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,
    senha TEXT NOT NULL
);

CREATE TABLE motos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    placa TEXT NOT NULL,
    modelo TEXT NOT NULL,
    ano INTEGER NOT NULL,
    disponivel BOOLEAN DEFAULT 1
);

CREATE TABLE clientes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    email TEXT,
    telefone TEXT
);

CREATE TABLE locacoes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cliente_id INTEGER NOT NULL,
    moto_id INTEGER NOT NULL,
    data_inicio TEXT NOT NULL,
    data_fim TEXT,
    FOREIGN KEY (cliente_id) REFERENCES clientes (id),
    FOREIGN KEY (moto_id) REFERENCES motos (id)
);