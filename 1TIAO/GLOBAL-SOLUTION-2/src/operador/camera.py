"""Câmera simulada da faixa (spec 2026-11-17 §2, §6).

Toca os clipes já processados pela visão (anotados e borrados), escolhendo pelo modo atual do nó. Os clipes do Veo 3
são SINTÉTICOS e aparecem rotulados assim; enquanto eles não chegam, usa os vídeos reais do Pexels já anotados.
"""
from __future__ import annotations

import base64
import html
import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
VEO3 = RAIZ / "data" / "processed" / "veo3"
REAIS = RAIZ / "data" / "processed" / "camera_real"
# vídeos reais já anotados e borrados (notebooks 07 e 09) → cópia H.264 para tocar no navegador
FONTES_REAIS = {"cdmx_pexels_25775484": ("visao_cdmx_borrado.mp4", "pedestre"),
                "cadeirante_pexels_6646677": ("visao_cadeirante_pexels_6646677_anotado.mp4", "cadeirante")}

MODO_PARA_CATEGORIAS = {
    "normal": ("normal", "normal_noite", "armadilha"),
    "pedestre": ("cadeirante", "andador", "muleta", "bengala", "surpreendido", "conflito", "pedestre"),
    "escola": ("escola",),
    "chuva": ("chuva", "alagamento"),
    "ambulancia": ("ambulancia",),
}
NOMES_EVENTO = {"suspeita_acidente": "Suspeita de acidente", "pcd_na_faixa": "Pessoa com auxílio de mobilidade",
                "conflito_veiculo_pedestre": "Conflito veículo × pedestre", "bloqueio_faixa": "Faixa bloqueada",
                "pedestre_na_faixa": "Pedestre na faixa"}
NOMES_MODO = {"normal": "Normal", "pedestre": "Pedestre", "escola": "Escola", "chuva": "Chuva",
              "ambulancia": "Ambulância"}


@dataclass(frozen=True)
class Clipe:
    nome: str
    categoria: str
    video: Path | None
    eventos: list
    sintetico: bool


def categoria(nome: str) -> str:
    return re.sub(r"_\d+$", "", Path(nome).stem)


def _h264(entrada: Path, saida: Path) -> bool:
    ff = shutil.which("ffmpeg")
    if ff is None or not entrada.exists():
        return False
    saida.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([ff, "-y", "-loglevel", "error", "-i", str(entrada), "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    "-vf", "scale=-2:720", "-movflags", "+faststart", "-an", str(saida)], check=True)
    return True


def clipes_disponiveis(veo3: Path = VEO3, reais: Path = REAIS) -> list[Clipe]:
    """Clipes sintéticos processados; sem nenhum, os vídeos reais de demonstração (convertidos na 1ª vez)."""
    saida = []
    for v in sorted(veo3.glob("*_anotado.mp4")):
        nome = v.name.removesuffix("_anotado.mp4")
        ev = veo3 / f"{nome}_eventos.json"
        eventos = json.loads(ev.read_text(encoding="utf-8")) if ev.exists() else []
        saida.append(Clipe(nome, categoria(nome), v, eventos, True))
    if saida:
        return saida
    for nome, (origem, cat) in FONTES_REAIS.items():
        destino = reais / f"{nome}.mp4"
        if destino.exists() or _h264(RAIZ / "data" / "processed" / origem, destino):
            saida.append(Clipe(nome, cat, destino, [], False))
    return saida


def clipe_para_modo(modo: str | None, clipes: list[Clipe], indice: int = 0) -> Clipe | None:
    """O `indice`-ésimo clipe (circular) das categorias do modo; sem nenhum dessas, qualquer clipe."""
    if not clipes:
        return None
    do_modo = [c for c in clipes if c.categoria in MODO_PARA_CATEGORIAS.get(modo or "", ())] or clipes
    return do_modo[indice % len(do_modo)]


def html_player(clipe: Clipe, modo: str | None, video_b64: str | None = None) -> str:
    """Player com as sobreposições do operador: câmera, modo do nó, rótulo da fonte e os eventos da visão, que acendem
    quando o vídeo passa pelo segundo deles."""
    if video_b64 is None:
        video_b64 = base64.b64encode(clipe.video.read_bytes()).decode() if clipe.video else ""
    fonte = "clipe sintético (Veo 3) · processado pela visão" if clipe.sintetico else \
        "vídeo real (Pexels) · demonstração, rostos e placas borrados"
    eventos = [{"rotulo": NOMES_EVENTO.get(e["tipo"], e["tipo"]), "segundo": e["segundo"],
                "alerta": e["tipo"] in ("suspeita_acidente", "conflito_veiculo_pedestre")}
               for e in clipe.eventos if e["tipo"] in NOMES_EVENTO]
    return f"""
<div id="cam" style="position:relative;font-family:Montserrat,system-ui,sans-serif;background:#1A1D21;border-radius:16px;overflow:hidden">
  <video id="v" src="data:video/mp4;base64,{video_b64}" autoplay muted loop playsinline style="width:100%;max-height:520px;object-fit:contain;background:#000;display:block"></video>
  <div style="position:absolute;top:12px;left:12px;background:rgba(26,29,33,.8);color:#F4F4EF;padding:6px 12px;border-radius:999px;font-size:13px;font-weight:600">
    ● CÂM 01 · Largo da Concórdia</div>
  <div style="position:absolute;top:12px;right:12px;background:#00C27A;color:#1A1D21;padding:6px 12px;border-radius:999px;font-size:13px;font-weight:700">
    Modo do nó: {html.escape(NOMES_MODO.get(modo or "", "sem sinal"))}</div>
  <div id="ev" style="position:absolute;left:12px;bottom:44px;display:flex;flex-direction:column;gap:6px"></div>
  <div style="position:absolute;left:0;right:0;bottom:0;background:rgba(26,29,33,.85);color:#9aa1aa;padding:8px 12px;font-size:12px">
    {html.escape(fonte)} · {html.escape(clipe.nome)}</div>
</div>
<script>
const EV = {json.dumps(eventos, ensure_ascii=False)};
const v = document.getElementById("v"), caixa = document.getElementById("ev");
v.addEventListener("timeupdate", () => {{
  caixa.innerHTML = "";
  for (const e of EV) {{
    if (v.currentTime >= e.segundo && v.currentTime < e.segundo + 4) {{
      const d = document.createElement("div");
      d.textContent = (e.alerta ? "⚠ " : "") + e.rotulo + " · " + e.segundo.toFixed(1) + " s";
      d.style.cssText = "padding:6px 12px;border-radius:8px;font-size:13px;font-weight:600;color:#1A1D21;background:" +
        (e.alerta ? "#E63946;color:#fff" : "#FFB000");
      caixa.appendChild(d);
    }}
  }}
}});
</script>"""
