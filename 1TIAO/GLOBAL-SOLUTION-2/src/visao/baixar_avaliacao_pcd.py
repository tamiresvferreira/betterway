"""Baixa as imagens do conjunto de avaliação de PCD a partir de data/avaliacao_pcd/FONTES.csv.

As imagens (pessoas identificáveis, ainda que com licença livre) não vão para o Git: o repositório guarda só a lista
de fontes (autor, licença, link) e os rótulos conferidos à mão (rotulos.csv). Uso:
    python src/visao/baixar_avaliacao_pcd.py          (a partir de 1TIAO/GLOBAL-SOLUTION-2/)
"""
import csv
import time
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
PASTA = RAIZ / "data" / "avaliacao_pcd"
UA = {"User-Agent": "GS-FIAP-estudo-b/1.0 (projeto academico)"}


def main():
    (PASTA / "img").mkdir(parents=True, exist_ok=True)
    fontes = list(csv.DictReader(open(PASTA / "FONTES.csv", encoding="utf-8-sig"), delimiter=";"))
    for r in fontes:
        destino = PASTA / "img" / r["arquivo"]
        if destino.exists():
            continue
        destino.write_bytes(urllib.request.urlopen(urllib.request.Request(r["url_640px"], headers=UA), timeout=60).read())
        time.sleep(1.5)   # respeita o limite de requisições do Wikimedia Commons
    print(f"{len(fontes)} imagens em {PASTA / 'img'}")


if __name__ == "__main__":
    main()
