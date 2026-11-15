"""Kaplan-Meier e log-rank: exemplos calculados À MÃO e conferência com o lifelines."""

from __future__ import annotations

import numpy as np
import pytest
from lifelines import KaplanMeierFitter
from lifelines.statistics import logrank_test, multivariate_logrank_test

from sobrevivencia import km as K


# ------------------------------------------------------------------------------------
# Exemplo à mão: 5 assinantes -> tempos 2(E) 3(E) 3(c) 5(E) 7(c)
#   t=2: n=5, d=1 -> S = 4/5 = 0.8            Greenwood: 1/(5*4)  = 0.05
#   t=3: n=4, d=1 -> S = 0.8*3/4 = 0.6        Greenwood: 1/(4*3)  = 0.083333
#   t=5: n=2, d=1 -> S = 0.6*1/2 = 0.3        Greenwood: 1/(2*1)  = 0.5
#   G(5) = 0.633333 ; se_loglog = sqrt(G)/|ln 0.3| = 0.66100
#   IC log-log 95% = S^exp(+-1.96*se) = [0.01229 ; 0.71917]
# ------------------------------------------------------------------------------------
DUR = [2, 3, 3, 5, 7]
EV = [1, 1, 0, 1, 0]


def test_km_exemplo_a_mao_valores_de_S():
    km = K.km_curve(DUR, EV)
    np.testing.assert_allclose(km.t, [2, 3, 5])
    np.testing.assert_allclose(km.n_risco, [5, 4, 2])
    np.testing.assert_allclose(km.S, [0.8, 0.6, 0.3])


def test_km_exemplo_a_mao_greenwood_e_ic_loglog():
    km = K.km_curve(DUR, EV)
    np.testing.assert_allclose(km.g, [0.05, 0.05 + 1 / 12, 0.05 + 1 / 12 + 0.5])
    s, lo, hi = km.em(5)
    assert s == pytest.approx(0.3)
    assert lo == pytest.approx(0.01229, abs=2e-4)
    assert hi == pytest.approx(0.71917, abs=2e-4)


def test_km_avaliacao_entre_eventos_e_antes_do_primeiro():
    km = K.km_curve(DUR, EV)
    assert km.em(1.0)[0] == 1.0
    assert km.em(2.5)[0] == pytest.approx(0.8)
    assert km.em(100)[0] == pytest.approx(0.3)  # S não cai com censura ao fim
    assert km.em_risco(3) == 4 and km.em_risco(5) == 2 and km.em_risco(8) == 0


def test_km_confere_com_lifelines_em_dados_reais(df):
    sub = df[df["canal"] == "midia_paga"]
    ours = K.km_curve(sub["duracao_meses"], sub["evento"])
    kmf = KaplanMeierFitter().fit(sub["duracao_meses"], sub["evento"])
    for h in (3, 6, 12, 18):
        s_l = float(kmf.survival_function_at_times(h).iloc[0])
        assert ours.em(h)[0] == pytest.approx(s_l, abs=1e-9)
        ci = kmf.confidence_interval_
        row = ci[ci.index <= h].iloc[-1]
        s, lo, hi = ours.em(h)
        assert lo == pytest.approx(float(row.iloc[0]), abs=1e-6)
        assert hi == pytest.approx(float(row.iloc[1]), abs=1e-6)


# ------------------------------------------------------------------------------------
# Log-rank à mão: A = {1,3,5} (todos eventos) ; B = {2,4,6} (todos eventos)
#   t=1: nA=3 nB=3 d=1  E_A=3/6      V=(1*5/5)*(3*3)/36 = 1/4
#   t=2: nA=2 nB=3 d=1  E_A=2/5      V=(2*3)/25         = 6/25
#   t=3: nA=2 nB=2 d=1  E_A=2/4      V=(2*2)/16         = 1/4
#   t=4: nA=1 nB=2 d=1  E_A=1/3      V=(1*2)/9          = 2/9
#   t=5: nA=1 nB=1 d=1  E_A=1/2      V=(1*1)/4          = 1/4
#   t=6: nA=0 nB=1 d=1  E_A=0        V=0
#   O_A=3 ; E_A=67/30 ; V=1091/900 ; chi2=(23/30)^2/(1091/900)=529/1091
# ------------------------------------------------------------------------------------
def test_logrank_exemplo_a_mao():
    dur = [1, 3, 5, 2, 4, 6]
    ev = [1] * 6
    g = ["A", "A", "A", "B", "B", "B"]
    r = K.logrank(dur, ev, g)
    assert r["observados"]["A"] == 3
    assert r["esperados"]["A"] == pytest.approx(67 / 30)
    assert r["chi2"] == pytest.approx(529 / 1091)
    assert r["df"] == 1
    assert r["p"] == pytest.approx(0.4862, abs=2e-3)


def test_logrank_confere_com_lifelines_dois_e_varios_grupos(df):
    sub = df[df["plano"].isin(["mensal", "combo"])]
    r = K.logrank(sub["duracao_meses"], sub["evento"], sub["plano"])
    ref = logrank_test(sub.loc[sub.plano == "mensal", "duracao_meses"],
                       sub.loc[sub.plano == "combo", "duracao_meses"],
                       sub.loc[sub.plano == "mensal", "evento"],
                       sub.loc[sub.plano == "combo", "evento"])
    assert r["chi2"] == pytest.approx(ref.test_statistic, rel=1e-6)

    r6 = K.logrank(df["duracao_meses"], df["evento"], df["canal"])
    ref6 = multivariate_logrank_test(df["duracao_meses"], df["canal"], df["evento"])
    assert r6["chi2"] == pytest.approx(ref6.test_statistic, rel=1e-6)
    assert r6["df"] == 5


def test_holm_nunca_menos_conservador_que_o_bruto(df):
    pares = K.logrank_pares_holm(df["duracao_meses"], df["evento"], df["canal"])
    assert len(pares) == 15
    for x in pares:
        assert x["p_holm"] >= x["p"] - 1e-12
        assert x["p_holm"] <= 1.0
    # Holm só pode derrubar significâncias, nunca criar
    assert sum(x["significativo_holm"] for x in pares) <= sum(x["significativo_bruto"] for x in pares)


def test_rmst_exemplo_a_mao():
    # S=1 em [0,2), 0.8 em [2,3), 0.6 em [3,5), 0.3 em [5,7]
    km = K.km_curve(DUR, EV)
    assert K.rmst(km, 7) == pytest.approx(2 * 1 + 1 * 0.8 + 2 * 0.6 + 2 * 0.3)
    assert K.rmst(km, 2.5) == pytest.approx(2 + 0.5 * 0.8)


def test_hazard_por_idade_taxa_constante_exponencial():
    rng = np.random.default_rng(0)
    t = rng.exponential(1 / 0.1, 40_000)
    h = K.hazard_por_idade(t, np.ones_like(t), max_idade=6)
    for linha in h:
        assert linha["taxa"] == pytest.approx(0.1, rel=0.12)
