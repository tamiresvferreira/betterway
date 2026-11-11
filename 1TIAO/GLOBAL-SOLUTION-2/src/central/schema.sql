-- Banco do projeto (SQLite): data/processed/via_segura.db

CREATE TABLE IF NOT EXISTS sinistros (
    id            INTEGER PRIMARY KEY,
    data_hora     TEXT,
    latitude      REAL,
    longitude     REAL,
    tipo          TEXT,      -- ex.: atropelamento, colisão
    fatal         INTEGER,   -- 1 = fatal, 0 = não fatal
    tipo_vitima   TEXT,
    logradouro    TEXT,
    cluster_id    INTEGER REFERENCES clusters(id)
);

CREATE TABLE IF NOT EXISTS clusters (
    id              INTEGER PRIMARY KEY,
    nome            TEXT,
    lat_centro      REAL,
    lon_centro      REAL,
    n_nao_fatais    INTEGER,
    n_fatais        INTEGER,
    extensao_m      REAL,
    indice_cet      REAL     -- extensão ÷ (não fatais + 3 × fatais); menor = mais crítico
);

CREATE TABLE IF NOT EXISTS pontos_alagamento (
    id          INTEGER PRIMARY KEY,
    nome        TEXT,
    latitude    REAL,
    longitude   REAL,
    ocorrencias_ultimo_ano INTEGER,
    fonte       TEXT
);

-- O que o nó fez e por quê
CREATE TABLE IF NOT EXISTS eventos (
    id          INTEGER PRIMARY KEY,
    data_hora   TEXT DEFAULT (datetime('now', 'localtime')),
    no_id       TEXT,       -- ex.: celso-garcia-01
    origem      TEXT,       -- yolo, botao, previsao, ambulancia
    modo        TEXT,       -- normal, pedestre, escola, chuva, ambulancia
    detalhe     TEXT
);

-- Alertas enviados (SAMU, polícia, CET) — SIMULADOS
CREATE TABLE IF NOT EXISTS alertas (
    id          INTEGER PRIMARY KEY,
    data_hora   TEXT DEFAULT (datetime('now', 'localtime')),
    no_id       TEXT,
    destino     TEXT,
    mensagem    TEXT,
    simulado    INTEGER DEFAULT 1
);
