"""Processa os clipes SINTÉTICOS (Veo 3) da câmera simulada (spec 2026-11-17 §3).

Para cada `data/raw/video/veo3/<clipe>.mp4`:
- detecta com YOLO-World + ByteTrack, o modelo ajustado (cadeira de rodas) e a pose (rostos), com cache;
- grava o vídeo anotado e BORRADO em `data/processed/veo3/<clipe>_anotado.mp4` (H.264; fora do Git);
- grava os eventos em `eventos` com video_id `veo3_<clipe>`;
- grava a avaliação esperado × obtido em `docs/evidencias/operador/avaliacao_clipes.csv`.

    python src/visao/processar_clipes.py                 # todos os clipes
    python src/visao/processar_clipes.py cadeirante_01   # só um

A faixa vem de `src/visao/faixa_veo3.json` (a imagem-base de todos os clipes) ou de `src/visao/faixas_veo3/<clipe>.json`.
Os clipes são dados SINTÉTICOS: a avaliação fica separada dos resultados com vídeo real (regra 8).
"""
from __future__ import annotations

import json
import re
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

import visao as vs

RAIZ = Path(__file__).resolve().parents[2]
CLIPES = RAIZ / "data" / "raw" / "video" / "veo3"
SAIDA = RAIZ / "data" / "processed" / "veo3"
MODELS = RAIZ / "models"
FAIXA_BASE = Path(__file__).with_name("faixa_veo3.json")
FAIXAS = Path(__file__).with_name("faixas_veo3")
AVALIACAO = RAIZ / "docs" / "evidencias" / "operador" / "avaliacao_clipes.csv"
BANCO = RAIZ / "data" / "processed" / "seguranca_viaria.db"

# categoria → o que a visão deve encontrar (None = não avaliado nesse item)
ESPERADO = {
    "normal": dict(auxilio=None, suspeita=False, conflito=None),
    "normal_noite": dict(auxilio=None, suspeita=False, conflito=None),
    "cadeirante": dict(auxilio="wheelchair", suspeita=False, conflito=None),
    "andador": dict(auxilio="walker", suspeita=False, conflito=None),
    "muleta": dict(auxilio="crutch", suspeita=False, conflito=None),
    "bengala": dict(auxilio="cane", suspeita=False, conflito=None),
    "surpreendido": dict(auxilio=None, suspeita=False, conflito=None),
    "conflito": dict(auxilio=None, suspeita=False, conflito=True),
    "chuva": dict(auxilio=None, suspeita=False, conflito=None),
    "alagamento": dict(auxilio=None, suspeita=False, conflito=None),
    "escola": dict(auxilio=None, suspeita=False, conflito=None),
    "ambulancia": dict(auxilio=None, suspeita=False, conflito=None),
    "suspeita_acidente": dict(auxilio=None, suspeita=True, conflito=None),
    "infracao": dict(auxilio=None, suspeita=False, conflito=None),
    "suspeita_bike": dict(auxilio=None, suspeita=True, conflito=None),
    "armadilha": dict(auxilio=None, suspeita=False, conflito=None),
}


def categoria_do_clipe(nome: str) -> str:
    """`cadeirante_01` → `cadeirante`; `normal_noite_01.mp4` → `normal_noite`. Desconhecida → ValueError."""
    base = re.sub(r"_\d+$", "", Path(nome).stem)
    if base not in ESPERADO:
        raise ValueError(f"categoria desconhecida no nome do clipe: {nome!r} (use categoria_nn.mp4)")
    return base


def avaliar(categoria: str, eventos) -> dict:
    """Compara o que a visão encontrou com o esperado da categoria. `None` no esperado = não conta.
    Auxílio esperado None quer dizer que NENHUM auxílio deve aparecer (testa falso alarme)."""
    esp = ESPERADO[categoria]
    auxilios = sorted({e.payload.get("auxilio") for e in eventos if e.tipo == "pcd_na_faixa"} - {None})
    obtido = dict(auxilio=auxilios, suspeita=any(e.tipo == "suspeita_acidente" for e in eventos),
                  conflito=any(e.tipo == "conflito_veiculo_pedestre" for e in eventos))
    itens = {"auxilio": (esp["auxilio"] in auxilios) if esp["auxilio"] else not auxilios,
             "suspeita": obtido["suspeita"] == esp["suspeita"]}
    if esp["conflito"] is not None:
        itens["conflito"] = obtido["conflito"] == esp["conflito"]
    return {"categoria": categoria, "auxilio_esperado": esp["auxilio"] or "nenhum",
            "auxilio_obtido": ",".join(auxilios) or "nenhum", "suspeita_esperada": esp["suspeita"],
            "suspeita_obtida": obtido["suspeita"], "conflito_obtido": obtido["conflito"],
            "pessoas_na_faixa": sum(e.tipo == "pedestre_na_faixa" for e in eventos), "acerto": all(itens.values())}


def faixa_do_clipe(nome: str, largura: int, altura: int) -> tuple[vs.Faixa, list | None]:
    """Faixa (reescalada para o vídeo) e o polígono da pista, se houver."""
    proprio = FAIXAS / f"{Path(nome).stem}.json"
    caminho = proprio if proprio.exists() else FAIXA_BASE
    if not caminho.exists():
        raise FileNotFoundError(f"marque a faixa da imagem-base em {FAIXA_BASE.relative_to(RAIZ)}")
    d = json.loads(caminho.read_text(encoding="utf-8"))
    faixa = vs.Faixa.de_dict(d)
    sx, sy = largura / faixa.resolucao[0], altura / faixa.resolucao[1]
    pista = [(x * sx, y * sy) for x, y in d["pista"]] if d.get("pista") else None
    faixa = faixa.para_resolucao(largura, altura)
    object.__setattr__(faixa, "desenhar", d.get("desenhar_faixa", True))   # sem faixa no quadro: não desenha
    return faixa, pista


def ambulancia_por_track(df):
    """Um veículo reconhecido como ambulância em algum quadro é ambulância do começo ao fim (no início ela entra
    pela borda e só o teto aparece, e a regra de cor ainda não a reconhece)."""
    if df.empty or "track_id" not in df:
        return df
    yw = (df.fonte == "yolo_world") & df.track_id.notna()
    ambs = set(df.loc[yw & (df.classe == "ambulance"), "track_id"])
    veiculo = df.classe.isin(["car", "bus", "truck", "ambulance"])
    df = df.copy()
    df.loc[yw & veiculo & df.track_id.isin(ambs), "classe"] = "ambulance"
    return df


def _detectar(video: Path, cache: Path, max_quadros: int | None = None):
    import pandas as pd
    if cache.exists():
        return ambulancia_por_track(pd.read_parquet(cache))
    from ultralytics import YOLO
    import detector
    ft, pose = YOLO(str(MODELS / "pcd_yolo11s.pt")), YOLO(str(MODELS / "yolo11n-pose.pt"))
    linhas = []
    for i, img, dets in detector.detectar(video):
        if max_quadros is not None and i >= max_quadros:
            break
        linhas += [dict(quadro=i, fonte="yolo_world", classe=d.classe, x1=d.caixa[0], y1=d.caixa[1], x2=d.caixa[2],
                        y2=d.caixa[3], conf=d.conf, track_id=d.track_id) for d in dets]
        r = ft.predict(img, conf=0.1, verbose=False)[0]
        linhas += [dict(quadro=i, fonte="ajustado", classe=r.names[c], x1=b[0], y1=b[1], x2=b[2], y2=b[3], conf=p,
                        track_id=None)
                   for b, c, p in zip(r.boxes.xyxy.tolist(), r.boxes.cls.int().tolist(), r.boxes.conf.tolist())]
        r = pose.predict(img, conf=0.1, verbose=False)[0]
        if r.keypoints is not None and r.keypoints.conf is not None:
            linhas += [dict(quadro=i, fonte="pose", classe="face", x1=f.caixa[0], y1=f.caixa[1], x2=f.caixa[2],
                            y2=f.caixa[3], conf=1.0, track_id=None)
                       for f in vs.rostos_pela_pose(r.keypoints.xy.cpu().numpy(), r.keypoints.conf.cpu().numpy(),
                                                    r.boxes.xyxy.tolist(), i)]
        linhas += [dict(quadro=i, fonte="pose", classe="person", x1=b[0], y1=b[1], x2=b[2], y2=b[3], conf=1.0,
                        track_id=None) for b in r.boxes.xyxy.tolist()]
    df = pd.DataFrame(linhas, columns=["quadro", "fonte", "classe", "x1", "y1", "x2", "y2", "conf", "track_id"])
    cache.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(cache, index=False)
    return ambulancia_por_track(df)


def _preparar(df):
    import pandas as pd
    tid = lambda v: None if pd.isna(v) else int(v)  # noqa: E731
    yw = [vs.Deteccao(int(r.quadro), r.classe, (r.x1, r.y1, r.x2, r.y2), float(r.conf), tid(r.track_id))
          for r in df[df.fonte == "yolo_world"].itertuples()]
    aux = []
    for q, g in df[df.fonte == "ajustado"].groupby("quadro"):
        aux += vs.auxilios_do_ajustado(g[["x1", "y1", "x2", "y2"]].values.tolist(), g.classe.tolist(), g.conf.tolist(),
                                       int(q))
    extras = [vs.Deteccao(int(r.quadro), "face" if r.classe == "face" else "person", (r.x1, r.y1, r.x2, r.y2), 1.0,
                          None)
              for r in df[(df.fonte == "pose") | ((df.fonte == "ajustado") & (df.conf >= 0.1))].itertuples()]
    return yw, aux, extras


def para_h264(entrada: Path, saida: Path) -> Path:
    """Converte para H.264 (o navegador não toca mp4v). Sem ffmpeg no sistema, mantém o arquivo original."""
    ff = shutil.which("ffmpeg")
    if ff is None:
        print("aviso: ffmpeg não encontrado; o vídeo fica em mp4v (pode não tocar no navegador)")
        entrada.replace(saida)
        return saida
    subprocess.run([ff, "-y", "-loglevel", "error", "-i", str(entrada), "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    "-movflags", "+faststart", "-an", str(saida)], check=True)
    entrada.unlink()
    return saida


def processar(video: Path, con=None, max_quadros: int | None = None, saida_dir: Path = SAIDA) -> tuple[list, dict]:
    """Processa um clipe: (eventos, avaliação). Grava o vídeo anotado e, com `con`, os eventos."""
    import cv2
    nome = video.stem
    categoria = categoria_do_clipe(nome)
    fps, w, h, _ = vs.ler_video(video)
    faixa, pista = faixa_do_clipe(nome, w, h)
    yw, aux, extras = _preparar(_detectar(video, saida_dir / f"{nome}_deteccoes.parquet", max_quadros))
    analise = vs.sem_condutores(vs.sem_bicicleta_na_cadeira(yw + aux))
    auxilios = vs.auxilios_por_pessoa(analise)
    pcd = set(auxilios)
    trav = vs.travessias(analise, faixa, fps, pcd)
    conf = vs.conflitos(analise, faixa, fps, pcd)
    sus = vs.suspeitas_de_queda(analise, faixa, fps, pista=pista)
    eventos = vs.eventos_de(trav, conf, vs.bloqueios(analise, faixa, fps), pcd, analise, faixa, fps, suspeitas_=sus)
    if con is not None:
        vs.migrar(con)
        vs.substituir_eventos(con, eventos, f"veo3_{nome}")
    # vídeo anotado: borra antes de desenhar (vs.anotar); nenhum quadro sai sem borrão
    por_q, ext_q = {}, {}
    for d in yw + aux:
        por_q.setdefault(d.quadro, []).append(d)
    for d in extras:
        ext_q.setdefault(d.quadro, []).append(d)
    kmh = {c.track_veiculo: c.velocidade_kmh for c in conf if c.velocidade_kmh is not None}
    saida_dir.mkdir(parents=True, exist_ok=True)
    tmp, escritor = saida_dir / f"{nome}_tmp.mp4", None
    _, _, _, quadros = vs.ler_video(video)
    for i, img in enumerate(quadros):
        if max_quadros is not None and i >= max_quadros:
            break
        a = vs.anotar(img, por_q.get(i, []), faixa if getattr(faixa, "desenhar", True) else None, auxilios, kmh,
                      privadas_extra=ext_q.get(i, []))
        if escritor is None:
            escritor = cv2.VideoWriter(str(tmp), cv2.VideoWriter_fourcc(*"mp4v"), fps, (a.shape[1], a.shape[0]))
        escritor.write(a)
    escritor.release()
    para_h264(tmp, saida_dir / f"{nome}_anotado.mp4")
    # eventos com o segundo, para a linha do tempo do player
    linha = [{"tipo": e.tipo, "segundo": round(e.quadro / fps, 2), "track_id": e.track_id, "payload": e.payload}
             for e in eventos if e.tipo != "contagem_minuto"]
    (saida_dir / f"{nome}_eventos.json").write_text(json.dumps(linha, ensure_ascii=False, default=vs._json_padrao),
                                                     encoding="utf-8")
    return eventos, {"clipe": nome, **avaliar(categoria, eventos)}


def main(argv=None):
    import pandas as pd
    sys.stdout.reconfigure(encoding="utf-8")
    nomes = (argv if argv is not None else sys.argv[1:])
    videos = [CLIPES / f"{n}.mp4" for n in nomes] if nomes else sorted(CLIPES.glob("*.mp4"))
    if not videos:
        sys.exit(f"nenhum clipe em {CLIPES}")
    con = sqlite3.connect(BANCO)
    linhas = []
    for v in videos:
        _, av = processar(v, con)
        linhas.append(av)
        print(f"{av['clipe']:<24} {'ok ' if av['acerto'] else 'ERRO'}  auxílio {av['auxilio_obtido']:<12} "
              f"suspeita {av['suspeita_obtida']}  pessoas na faixa {av['pessoas_na_faixa']}")
    novo = pd.DataFrame(linhas)
    if AVALIACAO.exists() and nomes:            # reprocessar um clipe atualiza só a linha dele
        antigo = pd.read_csv(AVALIACAO, sep=";", encoding="utf-8-sig")
        novo = pd.concat([antigo[~antigo.clipe.isin(novo.clipe)], novo]).sort_values("clipe")
    AVALIACAO.parent.mkdir(parents=True, exist_ok=True)
    novo.to_csv(AVALIACAO, sep=";", index=False, encoding="utf-8-sig")
    print(f"acertos: {int(novo.acerto.sum())}/{len(novo)} clipes SINTÉTICOS → {AVALIACAO.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
