"""Entradas da central: chuva prevista (Open-Meteo), pessoas na faixa (eventos da visão no banco) e ambulância simulada.
Nenhuma função levanta exceção por falha da fonte: devolve None/0 e a central segue ("sem dado")."""
from __future__ import annotations

import json
import sqlite3
import urllib.request
from datetime import datetime

URL_OPEN_METEO = ("https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&hourly=precipitation"
                  "&timezone=America%2FSao_Paulo&past_days=1&forecast_days=2")


def _obter_json(url: str) -> dict:
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "via-segura-sp/1.0"}),
                                timeout=10) as r:
        return json.load(r)


def chuva_prevista_mm_h(lat: float, lon: float, quando: datetime, obter=_obter_json) -> float | None:
    """Precipitação (mm na hora) prevista pelo Open-Meteo para a hora de `quando` (horário de São Paulo)."""
    try:
        h = obter(URL_OPEN_METEO.format(lat=lat, lon=lon))["hourly"]
        alvo = quando.strftime("%Y-%m-%dT%H:00")
        if alvo in h["time"]:
            v = h["precipitation"][h["time"].index(alvo)]
            return None if v is None else float(v)
    except Exception:   # rede, JSON, formato: a central segue sem o dado
        return None
    return None


def pessoas_na_faixa(con, desde: datetime | None = None, video_id: str | None = None,
                     tipo: str = "pedestre_na_faixa") -> int:
    """Quantos registros `tipo` a visão gravou (a partir de `desde` e/ou de um vídeo); `pcd_na_faixa` conta quem
    tem auxílio de mobilidade."""
    sql = "SELECT COUNT(*) FROM eventos WHERE origem = 'yolo' AND tipo = ?"
    args = [tipo]
    if desde is not None:
        sql += " AND timestamp >= ?"
        args.append(desde.isoformat(timespec="seconds"))
    if video_id is not None:
        sql += " AND json_extract(payload_json, '$.video_id') = ?"
        args.append(video_id)
    try:
        return int(con.execute(sql, args).fetchone()[0])
    except sqlite3.Error:
        return 0


def eta_ambulancia(t_s: float, distancia_inicial_m: float, velocidade_kmh: float) -> float:
    """Segundos até a ambulância (SIMULADA) chegar ao nó, `t_s` segundos depois de começar a se aproximar."""
    return max(0.0, distancia_inicial_m / (velocidade_kmh / 3.6) - t_s)
