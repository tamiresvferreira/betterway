"""Resumo do Estudo A: média (mín–máx) das 5 sementes e gráfico sem × com o sistema.

    python src/simulacao/resumo_estudo_a.py     # lê docs/evidencias/estudo_a/estudo_a_rodadas.csv
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

EVID = Path(__file__).resolve().parents[2] / "docs" / "evidencias" / "estudo_a"
SEM, COM = "#2a78d6", "#eb6834"      # paleta categórica validada (azul = sem o sistema, laranja = com)
TINTA, TINTA_2 = "#1f1f1e", "#5f5e5a"

# (comparação, métrica, título do painel, unidade)
PAINEIS = [("pedestre", "surpreendidos_reduzida_pct", "Pessoas com mobilidade reduzida\nsurpreendidas na faixa", "%"),
           ("ambulancia", "tempo_ambulancia_s", "Tempo da ambulância no trecho\n(média de 6 por rodada)", "s"),
           ("semaforo", "atraso_medio_carro_s", "Atraso médio por carro\n(tempo fixo × atuado)", "s"),
           ("pedestre", "atraso_medio_carro_s", "Custo da extensão para os carros\n(atraso médio por carro)", "s")]


def resumir(df: pd.DataFrame) -> pd.DataFrame:
    cols = ["atraso_medio_carro_s", "co2_medio_g_por_carro", "espera_media_pedestre_s", "surpreendidos_reduzida_pct",
            "surpreendidos_comum", "tempo_ambulancia_s", "tempo_ambulancia_max_s"]
    g = df.groupby(["comparacao", "sistema"])[cols]
    return g.mean().round(1).join(g.min().round(1).add_suffix("_min")).join(g.max().round(1).add_suffix("_max"))


def grafico(df: pd.DataFrame, saida: Path) -> None:
    plt.rcParams.update({"font.size": 10, "axes.edgecolor": "#c3c2b7", "axes.labelcolor": TINTA_2,
                         "xtick.color": TINTA_2, "ytick.color": TINTA_2})
    fig, eixos = plt.subplots(1, 4, figsize=(13, 3.6))
    for ax, (comp, met, titulo, un) in zip(eixos, PAINEIS):
        d = df[df["comparacao"] == comp].groupby("sistema")[met]
        for x, (sis, cor) in enumerate((("sem", SEM), ("com", COM))):
            vals = d.get_group(sis)
            m = vals.mean()
            ax.bar(x, m, width=0.55, color=cor, edgecolor="white", linewidth=2)
            ax.plot([x, x], [vals.min(), vals.max()], color=TINTA_2, linewidth=1.5)
            topo = max(vals.max(), m)
            ax.text(x, topo + 0.02 * max(df[df["comparacao"] == comp][met].max(), 1),
                    f"{m:.0f}{un}" if un == "%" else f"{m:.1f} {un}", ha="center", va="bottom",
                    color=TINTA, fontsize=10, fontweight="bold")
        ax.set_xticks([0, 1], ["sem o sistema", "com o sistema"])
        ax.set_title(titulo, fontsize=10, color=TINTA, loc="left")
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(axis="y", color="#e6e5df", linewidth=0.8)
        ax.set_axisbelow(True)
        ax.set_ylim(0, max(ax.get_ylim()[1], 1) * 1.12)
    fig.suptitle("Estudo A (SUMO, cruzamento calibrado pelo do Largo da Concórdia) — resultados ESPERADOS de "
                 "simulação; barras = média de 5 sementes, traço = mín–máx", fontsize=10, color=TINTA_2, x=0.01,
                 ha="left")
    fig.tight_layout(rect=(0, 0, 1, 0.92))
    fig.savefig(saida, dpi=150)
    plt.close(fig)


def main():
    df = pd.read_csv(EVID / "estudo_a_rodadas.csv", sep=";")
    r = resumir(df)
    r.to_csv(EVID / "estudo_a_resumo.csv", sep=";", encoding="utf-8-sig")
    grafico(df, EVID / "estudo_a_comparacoes.png")
    print(r[["atraso_medio_carro_s", "co2_medio_g_por_carro", "espera_media_pedestre_s", "surpreendidos_reduzida_pct",
             "surpreendidos_comum", "tempo_ambulancia_s", "tempo_ambulancia_max_s"]].to_string())


if __name__ == "__main__":
    main()
