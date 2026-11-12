-- Banco do projeto (SQLite): data/processed/seguranca_viaria.db
-- As 4 primeiras tabelas são criadas e preenchidas por
-- src/estudo_b_risco_vida/03_dbscan_pontos_criticos.ipynb (mesmo DDL; manter os dois iguais).

CREATE TABLE IF NOT EXISTS clusters (
    cluster_id      INTEGER PRIMARY KEY,
    lat_centro      REAL    NOT NULL,
    lon_centro      REAL    NOT NULL,
    n_fatais        INTEGER NOT NULL,
    n_nao_fatais    INTEGER NOT NULL,
    peso            INTEGER NOT NULL,             -- n_nao_fatais + 3 * n_fatais
    extensao_m      REAL    NOT NULL,             -- maior distância entre 2 pontos do grupo (aproximação)
    indice_cet      REAL    NOT NULL,             -- max(extensao_m, 20) / peso; menor = mais prioritário
    rank_prioridade INTEGER NOT NULL UNIQUE,      -- ranking geral (todos os grupos)
    rank_urbano     INTEGER UNIQUE,               -- nulo = rodovia ou pontos empilhados
    n_coords_distintas INTEGER NOT NULL,
    pct_via_urbana  REAL    NOT NULL,
    via_principal   TEXT,
    eps_m           REAL    NOT NULL,
    min_samples     INTEGER NOT NULL,
    criado_em       TEXT    NOT NULL
);
-- Entorno (acrescentado pelo notebook 04 com ALTER TABLE; raios a partir do centróide do grupo):
--   n_escolas_300m                  INTEGER   escolas públicas (EE, EMEF, EMEFM, EMEI, CEMEI, CEU) a até 300 m
--   distancia_escola_mais_proxima_m REAL
--   n_escolas_osm_300m              INTEGER   conferência: OSM amenity=school (inclui particulares) a até 300 m
--   n_semaforos_150m                INTEGER   nós OSM highway=traffic_signals a até 150 m (fonte principal)
--   n_travessias_semaforizadas_150m INTEGER   nós OSM crossing=traffic_signals / crossing:signals=yes a até 150 m
--   tem_semaforo                    INTEGER   0/1: OSM ou GeoSampa 2018 (comum) a até 150 m
--   fonte_semaforo                  TEXT      'osm' | 'geosampa_2018' | 'ambas' | NULL (nenhuma)

CREATE TABLE IF NOT EXISTS sinistros (
    id_sinistro   INTEGER PRIMARY KEY,
    data_sinistro TEXT    NOT NULL,               -- AAAA-MM-DD
    hora          INTEGER,                        -- 0-23; nulo se não informado
    latitude      REAL,
    longitude     REAL,
    coord_valida  INTEGER NOT NULL CHECK (coord_valida IN (0, 1)),
    fatal         INTEGER NOT NULL CHECK (fatal IN (0, 1)),
    tipo_via      TEXT,
    logradouro    TEXT,
    cluster_id    INTEGER REFERENCES clusters(cluster_id)   -- nulo = ruído ou sem coordenada
);
CREATE INDEX IF NOT EXISTS idx_sinistros_cluster ON sinistros(cluster_id);

-- O que o nó viu ou fez (preenchida pela visão, pelo ESP32 e pela central)
CREATE TABLE IF NOT EXISTS eventos (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp    TEXT    NOT NULL,
    origem       TEXT    NOT NULL CHECK (origem IN ('yolo', 'esp32', 'central')),
    cluster_id   INTEGER REFERENCES clusters(cluster_id),
    tipo         TEXT    NOT NULL,
    valor        REAL,
    payload_json TEXT
);

-- Alertas e mudanças de modo decididos pela central (SIMULADOS)
CREATE TABLE IF NOT EXISTS alertas (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp  TEXT    NOT NULL,
    cluster_id INTEGER REFERENCES clusters(cluster_id),
    modo       TEXT    NOT NULL CHECK (modo IN ('normal', 'pedestre', 'escola', 'chuva', 'ambulancia')),
    motivo     TEXT,
    risco      REAL,
    enviado    INTEGER NOT NULL DEFAULT 0 CHECK (enviado IN (0, 1))
);

-- Ainda não criada pelo notebook 03 (base do CGE, etapa de chuva)
CREATE TABLE IF NOT EXISTS pontos_alagamento (
    id          INTEGER PRIMARY KEY,
    nome        TEXT,
    latitude    REAL,
    longitude   REAL,
    ocorrencias_ultimo_ano INTEGER,
    fonte       TEXT
);
