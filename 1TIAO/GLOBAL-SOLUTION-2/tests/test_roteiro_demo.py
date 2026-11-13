"""Roteiros de demonstração e de teste do nó ESP32 (src/central/roteiro_demo.py)."""
import mensagens as m
import roteiro_demo as r


def test_demo_ordem_e_tempos_crescentes():
    p = r.roteiro()
    assert [t for t, _ in p] == sorted(t for t, _ in p)
    assert [c["modo"] for _, c in p][:6] == ["normal", "pedestre", "pedestre", "escola", "chuva", "chuva"]
    assert all(m.validar_comando(c) == [] for _, c in p)


def test_demo_ambulancia_eta_decrescente_ate_fim():
    amb = [c for _, c in r.roteiro() if c["modo"] == "ambulancia"]
    etas = [c["eta_s"] for c in amb if "eta_s" in c]
    assert etas == sorted(etas, reverse=True) and etas[-1] == 0 and amb[-1].get("fim") is True


def test_roteiro_de_teste_cobre_a_aceitacao():
    p = r.roteiro(teste=True)
    assert [t for t, _ in p] == sorted(t for t, _ in p)
    assert any(m.validar_comando(c) for _, c in p if "_pausa_s" not in c)   # o inválido de propósito
    assert p[-1][1].get("_pausa_s", 0) >= 130                               # 120 s sem central → normal
    modos = [c.get("modo") for _, c in p]
    assert {"pedestre", "escola", "chuva"} <= set(modos)
    amb = [c for _, c in p if c.get("modo") == "ambulancia"]
    assert amb[0].get("fim") is True and "eta_s" not in amb[0]     # "fim" isolado antes de qualquer ambulância
    assert not amb[-1].get("fim")                                  # a última ambulância fica sem fim (termina sozinha)
    assert any(c.get("eta_s", 99) <= 30 for c in amb)              # janela para testar o botão bloqueado


def test_publicar_sem_rede_usa_cliente_falso(monkeypatch):
    enviados, dormiu = [], []

    class Falso:
        def connect(self, *a, **k): pass
        def loop_start(self): pass
        def loop_stop(self): pass
        def disconnect(self): pass

        def publish(self, topico, dado, qos=0, retain=False):
            enviados.append((topico, qos))
            return type("R", (), {"wait_for_publish": lambda s, t=None: None})()

    monkeypatch.setattr(r, "_cliente", lambda: Falso())
    passos = r.roteiro()[:3] + [(200, {"_pausa_s": 5})]
    n = r.publicar(passos, dormir=dormiu.append)
    assert n == 3 and enviados[0] == (m.TOPICO_COMANDO, 1)
    assert sum(dormiu) == passos[2][0] + 5                    # espera entre passos + a pausa final
